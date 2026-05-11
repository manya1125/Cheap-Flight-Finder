let pollTimer = null;
let activeUser = null;

function setMessage(element, message, type) {
    if (!element) {
        return;
    }

    element.textContent = message;
    element.className = `form-msg ${type || ""}`.trim();
}

function byId(id) {
    return document.getElementById(id);
}

function on(id, eventName, handler) {
    const element = byId(id);
    if (element) {
        element.addEventListener(eventName, handler);
    }
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}

function formatCurrency(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) {
        return "\u20b90";
    }

    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
    }).format(amount);
}

function updateStats(stats) {
    if (!stats) {
        return;
    }

    if (typeof stats.subscriber_count === "number") {
        const subscriberCount = byId("subscriberCount");
        if (subscriberCount) {
            subscriberCount.textContent = stats.subscriber_count;
        }
    }
    if (typeof stats.wishlist_count === "number") {
        const wishlistCount = byId("wishlistCount");
        if (wishlistCount) {
            wishlistCount.textContent = stats.wishlist_count;
        }
    }
}

function fillSettings(user) {
    const alertFrequency = byId("alertFrequency");
    const preferredOrigin = byId("preferredOrigin");
    const maxPrice = byId("maxPrice");

    if (alertFrequency) {
        alertFrequency.value = user?.alert_frequency || "instant";
    }
    if (preferredOrigin) {
        preferredOrigin.value = user?.preferred_origin || "LON";
    }
    if (maxPrice) {
        maxPrice.value = user?.max_price ?? "";
    }
}

function renderAuthState() {
    const summary = byId("authSummary");
    const logoutBtn = byId("logoutBtn");
    const wishlist = byId("wishlist");

    if (activeUser) {
        if (summary) {
            summary.innerHTML = `
                <p class="auth-headline">Signed in as ${escapeHtml(activeUser.first_name)}.</p>
                <p class="panel-note">Your wishlist and alerts are now tied to ${escapeHtml(activeUser.email)}.</p>
            `;
        }
        if (logoutBtn) {
            logoutBtn.hidden = false;
        }
        fillSettings(activeUser);
        if (wishlist) {
            if (wishlist.classList.contains("empty-state")) {
                wishlist.textContent = "Loading your wishlist...";
            }
            loadWishlist();
        }
        return;
    }

    if (summary) {
        summary.innerHTML = `
            <p class="auth-headline">Sign up or log in to save routes.</p>
            <p class="panel-note">Imported subscribers can activate their account by registering with the same email.</p>
        `;
    }
    if (logoutBtn) {
        logoutBtn.hidden = true;
    }
    if (wishlist) {
        wishlist.className = "wishlist-list empty-state";
        wishlist.textContent = "Log in to load your wishlist.";
    }
    fillSettings(null);
}

function renderWishlist(items) {
    const container = byId("wishlist");
    if (!container) {
        return;
    }

    if (!items.length) {
        container.className = "wishlist-list empty-state";
        container.textContent = "No saved cities yet for this account.";
        return;
    }

    container.className = "wishlist-list";
    container.innerHTML = items
        .map((city) => `<div class="wishlist-item">${escapeHtml(city)}</div>`)
        .join("");
}

function renderResults(results) {
    const container = byId("results");
    if (!container) {
        return;
    }

    if (!results.length) {
        container.innerHTML = `<div class="empty-state result-empty">No results yet.</div>`;
        return;
    }

    container.innerHTML = results.map((result) => {
        if (!result.found) {
            return `
                <article class="result-card no-flights">
                    <p class="result-city">${escapeHtml(result.city)}</p>
                    <p class="result-price">No flights found</p>
                    <p class="result-meta">Threshold: ${formatCurrency(result.threshold)}</p>
                </article>
            `;
        }

        const cardClass = result.is_deal ? "deal" : "no-deal";
        const badge = result.is_deal
            ? `<span class="deal-badge">Deal found</span>`
            : `<span class="no-deal-badge">Above target</span>`;
        const stopover = result.via_city
            ? `Stop via ${escapeHtml(result.via_city)} (${escapeHtml(result.via_airport)})`
            : "Direct flight";

        return `
            <article class="result-card ${cardClass}">
                ${badge}
                <p class="result-city">${escapeHtml(result.city)}</p>
                <p class="result-price">${formatCurrency(result.price)}</p>
                <p class="result-meta">Origin: ${escapeHtml(result.origin || "LON")}</p>
                <p class="result-meta">${escapeHtml(result.from_city)} (${escapeHtml(result.from_airport)}) to ${escapeHtml(result.to_city)} (${escapeHtml(result.to_airport)})</p>
                <p class="result-meta">${escapeHtml(result.out_date)} to ${escapeHtml(result.return_date)}</p>
                <p class="result-meta">Target price: ${formatCurrency(result.threshold)}</p>
                <p class="result-meta">${stopover}</p>
            </article>
        `;
    }).join("");
}

function hydrateInitialUser() {
    const body = document.body.dataset;
    if (!body.userEmail) {
        return;
    }

    activeUser = {
        email: body.userEmail,
        first_name: body.userName || body.userEmail,
        alert_frequency: "instant",
        preferred_origin: "LON",
        max_price: null,
    };
}

function loadWishlist() {
    const msg = byId("wishlistMsg");

    if (!activeUser) {
        setMessage(msg, "Log in to view your wishlist.", "error");
        renderAuthState();
        return;
    }

    fetch("/wishlist")
        .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
        .then(({ ok, body }) => {
            if (!ok) {
                setMessage(msg, body.error || "Could not load wishlist.", "error");
                return;
            }

            renderWishlist(body.wishlist);
            setMessage(msg, "Wishlist loaded.", "success");
        })
        .catch(() => {
            setMessage(msg, "Could not load wishlist right now.", "error");
        });
}

function syncAuthStatus() {
    fetch("/auth/status")
        .then((response) => response.json())
        .then((data) => {
            activeUser = data.user;
            renderAuthState();
        })
        .catch(() => {
            renderAuthState();
        });
}

function loadSettings() {
    if (!activeUser) {
        fillSettings(null);
        return;
    }

    fetch("/api/settings")
        .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
        .then(({ ok, body }) => {
            if (!ok) {
                return;
            }
            activeUser = body.user;
            fillSettings(activeUser);
        });
}

function pollResults() {
    fetch("/search/status")
        .then((response) => response.json())
        .then((data) => {
            const progressText = byId("progressText");
            if (progressText) {
                progressText.textContent = `Checking fares... ${data.count} routes processed`;
            }
            renderResults(data.results);

            if (!data.running && data.done) {
                clearInterval(pollTimer);
                pollTimer = null;
                const progress = byId("progress");
                if (progress) {
                    progress.hidden = true;
                }

                const btn = byId("searchBtn");
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = "Search for Deals";
                }
            }
        })
        .catch(() => {
            clearInterval(pollTimer);
            pollTimer = null;
            const progress = byId("progress");
            if (progress) {
                progress.hidden = true;
            }

            const btn = byId("searchBtn");
            if (btn) {
                btn.disabled = false;
                btn.textContent = "Search for Deals";
            }
        });
}

function startSearch() {
    const btn = byId("searchBtn");
    const progress = byId("progress");
    const progressText = byId("progressText");
    if (!btn || !progress || !progressText) {
        return;
    }

    btn.disabled = true;
    btn.textContent = "Searching...";
    progress.hidden = false;
    progressText.textContent = "Starting fare scan...";
    renderResults([]);

    fetch("/search", { method: "POST" })
        .then((response) => response.json())
        .then((data) => {
            if (data.status === "unavailable") {
                progressText.textContent = data.error;
                btn.disabled = false;
                btn.textContent = "Search for Deals";
                return;
            }

            if (data.status === "already_running") {
                progressText.textContent = "A search is already running.";
                btn.disabled = false;
                btn.textContent = "Search for Deals";
                return;
            }

            pollTimer = setInterval(pollResults, 1500);
        })
        .catch(() => {
            btn.disabled = false;
            btn.textContent = "Search for Deals";
            progress.hidden = true;
        });
}

document.addEventListener("DOMContentLoaded", () => {
    hydrateInitialUser();
    renderAuthState();
    syncAuthStatus();
    loadSettings();

    on("searchBtn", "click", startSearch);
    on("loadWishlistBtn", "click", loadWishlist);

    on("logoutBtn", "click", () => {
        fetch("/logout", { method: "POST" })
            .then((response) => response.json())
            .then(() => {
                activeUser = null;
                setMessage(byId("loginMsg"), "Signed out.", "success");
                renderAuthState();
            });
    });

    on("registerForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("formMsg");
        setMessage(msg, "Creating account...", "");

        const payload = {
            firstName: byId("firstName").value.trim(),
            lastName: byId("lastName").value.trim(),
            email: byId("email").value.trim().toLowerCase(),
            password: byId("registerPassword").value,
        };

        fetch("/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (!ok) {
                    return;
                }

                activeUser = body.user;
                updateStats(body.stats);
                byId("registerForm")?.reset();
                byId("loginForm")?.reset();
                if (byId("resetEmail")) {
                    byId("resetEmail").value = activeUser.email;
                }
                renderAuthState();
                loadSettings();
            })
            .catch(() => {
                setMessage(msg, "Could not create the account right now.", "error");
            });
    });

    on("loginForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("loginMsg");
        setMessage(msg, "Signing in...", "");

        const payload = {
            email: byId("loginEmail").value.trim().toLowerCase(),
            password: byId("loginPassword").value,
        };

        fetch("/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (!ok) {
                    return;
                }

                activeUser = body.user;
                byId("loginForm")?.reset();
                if (byId("resetEmail")) {
                    byId("resetEmail").value = activeUser.email;
                }
                renderAuthState();
                loadSettings();
            })
            .catch(() => {
                setMessage(msg, "Could not sign in right now.", "error");
            });
    });

    on("settingsForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("settingsMsg");
        if (!activeUser) {
            setMessage(msg, "Log in to update settings.", "error");
            return;
        }

        setMessage(msg, "Saving settings...", "");

        const payload = {
            alertFrequency: byId("alertFrequency").value,
            preferredOrigin: byId("preferredOrigin").value.trim().toUpperCase(),
            maxPrice: byId("maxPrice").value.trim(),
        };

        fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (!ok) {
                    return;
                }

                activeUser = body.user;
                fillSettings(activeUser);
                renderAuthState();
            })
            .catch(() => {
                setMessage(msg, "Could not update settings right now.", "error");
            });
    });

    on("resetRequestForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("resetRequestMsg");
        setMessage(msg, "Preparing reset token...", "");

        const payload = {
            email: byId("resetEmail").value.trim().toLowerCase(),
        };

        fetch("/password-reset/request", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json())
            .then((body) => {
                const suffix = body.resetToken ? ` Token: ${body.resetToken}` : "";
                setMessage(msg, `${body.message}${suffix}`, "success");
            })
            .catch(() => {
                setMessage(msg, "Could not prepare a reset token right now.", "error");
            });
    });

    on("resetConfirmForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("resetConfirmMsg");
        setMessage(msg, "Updating password...", "");

        const payload = {
            token: byId("resetToken").value.trim(),
            password: byId("resetPassword").value,
        };

        fetch("/password-reset/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (ok) {
                    byId("resetConfirmForm")?.reset();
                }
            })
            .catch(() => {
                setMessage(msg, "Could not reset the password right now.", "error");
            });
    });

    on("deleteAccountForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("deleteMsg");
        if (!activeUser) {
            setMessage(msg, "Log in to delete your account.", "error");
            return;
        }

        setMessage(msg, "Deleting account...", "");

        const payload = {
            confirmation: byId("deleteConfirmation").value.trim(),
        };

        fetch("/account", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (!ok) {
                    return;
                }

                activeUser = null;
                updateStats(body.stats);
                byId("deleteAccountForm")?.reset();
                renderAuthState();
            })
            .catch(() => {
                setMessage(msg, "Could not delete the account right now.", "error");
            });
    });

    on("wishlistForm", "submit", (event) => {
        event.preventDefault();

        const msg = byId("wishlistMsg");
        if (!activeUser) {
            setMessage(msg, "Log in to save wishlist items.", "error");
            return;
        }

        setMessage(msg, "Saving wishlist item...", "");

        const payload = {
            city: byId("wishlistCity").value,
        };

        fetch("/wishlist/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json().then((body) => ({ ok: response.ok, body })))
            .then(({ ok, body }) => {
                setMessage(msg, ok ? body.message : body.error, ok ? "success" : "error");
                if (!ok) {
                    return;
                }

                updateStats(body.stats);
                renderWishlist(body.wishlist);
            })
            .catch(() => {
                setMessage(msg, "Could not save wishlist right now.", "error");
            });
    });
});
