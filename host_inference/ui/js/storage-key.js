// Keep private browser state inside the verified account's namespace.
export function storageKey(key) {
    const userId = window.archipelagoUserId;
    if (!userId) throw new Error('Sign in before accessing saved data.');
    return `archipelago_user_${userId}_${key}`;
}
