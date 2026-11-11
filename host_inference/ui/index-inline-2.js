        window.archipelagoAuthReady.then(async ({ config, supabase }) => {
            if (config && config.required) {
                const session = await window.archipelagoRequireSession();
                if (!session) return; // redirected to login
            }
            await updateHeaderAuthProfile();
        });

        async function updateHeaderAuthProfile() {
            try {
                let user = null;
                try {
                    const resp = await fetch("/api/auth/me", { cache: "no-store" });
                    if (resp.ok) {
                        const serverUser = await resp.json();
                        if (serverUser?.authenticated === true && serverUser.role) user = serverUser;
                    }
                } catch (_) {}

                const badge = document.getElementById("user-profile-badge");
                const loginLink = document.getElementById("auth-login-link");
                const roleLabel = document.getElementById("user-role-label");
                const nameLabel = document.getElementById("user-name-label");
                if (user?.authenticated === true && user.role) {
                    if (badge) { badge.classList.remove("hidden"); badge.classList.add("flex"); }
                    if (loginLink) loginLink.classList.add("hidden");
                    if (roleLabel) roleLabel.textContent = user.role || "Student";
                    if (nameLabel) nameLabel.textContent = user.username ? `(${user.username})` : "";
                } else {
                    if (badge) { badge.classList.add("hidden"); badge.classList.remove("flex"); }
                    if (loginLink) loginLink.classList.remove("hidden");
                }
            } catch (e) {
                console.warn("Could not check auth status:", e);
            }
        }
        window.updateHeaderAuthProfile = updateHeaderAuthProfile;

        // Run immediately as early as possible
        updateHeaderAuthProfile();
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", updateHeaderAuthProfile);
        }

        window.signOutSupabase = async function() {
            try {
                sessionStorage.removeItem("archipelago_local_user");
                localStorage.removeItem("archipelago_local_user");
                await fetch("/api/auth/session", { method: "DELETE", credentials: "same-origin" });
                const { supabase } = await window.archipelagoAuthReady;
                if (supabase) await supabase.auth.signOut();
            } catch (e) {
                console.warn(e);
            }
            window.location.replace("/login");
        };
