// Stream rendering helpers extracted from send-message.
// SmoothTypewriterStream paints grounded text word-by-word, and the two
// predicates decide whether a late model rewrite should replace first paint.

class SmoothTypewriterStream {
    constructor(renderFn, options = {}) {
        this.renderFn = renderFn;
        this.speed = options.speed || 10;
        this.targetText = '';
        this.displayedIndex = 0;
        this.timer = null;
        this.isTyping = false;
        this.shouldReduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.onLiveChange = options.onLiveChange || null;
    }

    reset() {
        if (this.timer) { clearTimeout(this.timer); this.timer = null; }
        this.isTyping = false;
        this.targetText = '';
        this.displayedIndex = 0;
        if (this.onLiveChange) this.onLiveChange(false);
    }

    update(fullText, { instant = false, forceTypewriter = false } = {}) {
        const next = fullText || '';
        const prev = this.targetText || '';
        // Hard replace (STREAM_DONE / different draft): paint instantly — no restart blink.
        const isHardReplace = instant
            || (prev.length > 0 && next.length > 0
                && !next.startsWith(prev.slice(0, Math.min(24, prev.length)))
                && !prev.startsWith(next.slice(0, Math.min(24, next.length))));
        this.targetText = next;
        // Live model tokens: always typewriter word-by-word (unless reduced motion).
        if (forceTypewriter && !this.shouldReduceMotion && !instant) {
            // If target shrank/reset (rewrite start), restart from 0.
            if (next.length < this.displayedIndex) {
                this.displayedIndex = 0;
            }
            if (this.onLiveChange) this.onLiveChange(true);
            if (!this.isTyping && this.displayedIndex < this.targetText.length) {
                this.start();
            }
            return;
        }
        // Large catch-up only for non-live paths (grounded first paint).
        if (this.shouldReduceMotion || isHardReplace || (!forceTypewriter && next.length - this.displayedIndex > 180)) {
            this.displayedIndex = this.targetText.length;
            if (this.timer) { clearTimeout(this.timer); this.timer = null; }
            this.isTyping = false;
            if (this.renderFn) this.renderFn(this.targetText);
            if (this.onLiveChange) this.onLiveChange(false);
            return;
        }
        if (this.onLiveChange) this.onLiveChange(true);
        if (!this.isTyping && this.displayedIndex < this.targetText.length) {
            this.start();
        }
    }

    start() {
        if (this.isTyping) return;
        this.isTyping = true;
        if (this.onLiveChange) this.onLiveChange(true);
        const step = () => {
            if (this.displayedIndex < this.targetText.length) {
                // One word (or short token) at a time for true typewriter stream.
                let nextIdx = this.displayedIndex + 1;
                while (nextIdx < this.targetText.length && nextIdx < this.displayedIndex + 12 && !/\s/.test(this.targetText[nextIdx - 1] || '')) {
                    // advance through non-space run, stop after first whitespace
                    if (/\s/.test(this.targetText[nextIdx])) {
                        nextIdx++;
                        break;
                    }
                    nextIdx++;
                }
                this.displayedIndex = Math.min(nextIdx, this.targetText.length);
                if (this.renderFn) this.renderFn(this.targetText.slice(0, this.displayedIndex));
                this.timer = setTimeout(step, this.speed);
            } else {
                this.isTyping = false;
                // Stay "live" until STREAM_DONE clears status — model may still be producing.
                if (this.onLiveChange) this.onLiveChange(true);
            }
        };
        step();
    }

    flush() {
        if (this.timer) { clearTimeout(this.timer); this.timer = null; }
        this.isTyping = false;
        this.displayedIndex = this.targetText.length;
        if (this.renderFn) this.renderFn(this.targetText);
        if (this.onLiveChange) this.onLiveChange(false);
    }

    stop() {
        if (this.timer) { clearTimeout(this.timer); this.timer = null; }
        this.isTyping = false;
        if (this.onLiveChange) this.onLiveChange(false);
    }
}

const _normText = (s) => String(s || '').replace(/\s+/g, ' ').trim();
const _shouldReplaceFinal = (incoming, current) => {
    const inc = _normText(incoming);
    const cur = _normText(current);
    if (!inc) return false;
    if (!cur) return true;
    if (inc === cur) return false;
    // Keep a solid first-paint study card over a thinner final.
    if (cur.length >= 160 && inc.length < Math.floor(cur.length * 0.55)) {
        return false;
    }
    // Keep first paint over title+[END] stubs.
    if (/^.{0,90}(\[END\]|\[DONE\]|THE END\.?)\s*$/i.test(inc) && inc.length < 140) {
        return false;
    }
    // Keep first paint over residual [S#] / citation-spam rewrites.
    const sHash = (inc.match(/\[S#?\]|\[S#\]\s*to|\bS#\b/gi) || []).length;
    const fakeCite = (inc.match(/\[(?:RWC|GPT|BART|Guanaco)[^\]]{0,16}\]/gi) || []).length;
    if (cur.length >= 120 && (sHash >= 2 || fakeCite >= 2)) {
        return false;
    }
    // Keep first paint when the model rewrite is dramatically longer
    // (rambling 0.5B dump) and the current card already looks complete.
    if (cur.length >= 200 && inc.length > Math.floor(cur.length * 1.8)) {
        const curEnds = /[.!?…]["'”’)]?\s*$/.test(cur);
        if (curEnds) return false;
    }
    return true;
};

export { SmoothTypewriterStream, _normText, _shouldReplaceFinal };
