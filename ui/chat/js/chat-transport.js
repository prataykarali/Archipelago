/** Decode the chat wire format without ever painting transport metadata. */
const START = '[STREAM_START]';
const REWRITE = '[MODEL_REWRITE]';
const DONE = '[STREAM_DONE]';
const CLEAN = '[CLEAN]';
const MAX_HEADER = 128 * 1024;
const MAX_FINAL = 2 * 1024 * 1024;
const BAD_RESPONSE = 'The server returned an incomplete or invalid answer. Please retry.';
const TRANSPORT_KEYS = ['routing', 'anchor_concept', 'prerequisites', 'render_graph', 'subgraph', 'inspector', 'pipeline'];

export class ChatTransport {
    constructor(contentType = '') {
        this.json = /(^|[/+])json\b/i.test(contentType);
        if (/text\/html/i.test(contentType)) throw new Error(BAD_RESPONSE);
        this.header = '';
        this.pending = '';
        this.started = false;
        this.final = false;
        this.sawText = false;
    }

    push(chunk) {
        if (!this.started) {
            this.header += chunk;
            const index = this.json ? -1 : this.header.indexOf(START);
            if ((index === -1 ? this.header.length : index) > MAX_HEADER) throw new Error(BAD_RESPONSE);
            if (index === -1) return [];
            let metadata;
            try { metadata = JSON.parse(this.header.slice(0, index)); }
            catch (_) { throw new Error(BAD_RESPONSE); }
            if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) throw new Error(BAD_RESPONSE);
            if (metadata.error) throw new Error('The answer service is unavailable. Please retry.');
            const rest = this.header.slice(index + START.length).replace(/^\n+/, '');
            this.header = '';
            this.started = true;
            return [{ type: 'metadata', value: metadata }, ...this.consume(rest)];
        }
        return this.consume(chunk);
    }

    consume(chunk, eof = false) {
        this.pending += chunk;
        const events = [];
        if (this.final) {
            if (this.pending.length > MAX_FINAL) throw new Error(BAD_RESPONSE);
            if (eof && this.pending.trim()) {
                this.sawText = true;
                events.push({ type: 'text', value: DONE + this.pending });
                this.pending = '';
            }
            return events;
        }
        const markers = [REWRITE, DONE, CLEAN];
        while (this.pending) {
            const matches = markers.map(tag => ({ tag, index: this.pending.indexOf(tag) }))
                .filter(item => item.index >= 0).sort((a, b) => a.index - b.index);
            if (matches.length) {
                const { tag, index } = matches[0];
                if (index) events.push(this.text(this.pending.slice(0, index)));
                this.pending = this.pending.slice(index + tag.length).replace(/^\n+/, '');
                if (tag === REWRITE) {
                    events.push({ type: 'text', value: REWRITE });
                } else {
                    this.final = true;
                    return [...events, ...this.consume('', eof)];
                }
                continue;
            }
            let hold = 0;
            if (!eof) {
                for (const marker of markers) {
                    for (let n = 1; n < marker.length; n++) {
                        if (this.pending.endsWith(marker.slice(0, n))) hold = Math.max(hold, n);
                    }
                }
            }
            const ready = this.pending.slice(0, this.pending.length - hold);
            this.pending = hold ? this.pending.slice(-hold) : '';
            if (ready) events.push(this.text(ready));
            break;
        }
        return events;
    }

    text(value) {
        if (value.trim()) this.sawText = true;
        return { type: 'text', value };
    }

    finish() {
        if (!this.started) {
            const raw = this.header.trim();
            if (!raw) throw new Error('The server returned an empty answer. Please retry.');
            let value;
            try { value = JSON.parse(raw); }
            catch (_) {
                if (this.json || /^[{[]/.test(raw) || raw.includes(START)) throw new Error(BAD_RESPONSE);
                return [this.text(raw)];
            }
            if (value && typeof value === 'object' && !Array.isArray(value)) {
                if ('error' in value || value.success === false) {
                    throw new Error('The answer service is unavailable. Please retry.');
                }
                const answer = ['answer', 'text', 'response'].map(key => value[key])
                    .find(item => typeof item === 'string' && item.trim());
                if (answer) {
                    const metadata = value.metadata && typeof value.metadata === 'object'
                        && !Array.isArray(value.metadata) ? [{ type: 'metadata', value: value.metadata }] : [];
                    return [...metadata, this.text(answer)];
                }
                if (TRANSPORT_KEYS.some(key => key in value)) throw new Error(BAD_RESPONSE);
            }
            // Genuine JSON answers are content, not transport metadata.
            return [this.text(raw)];
        }
        const events = this.consume('', true);
        if (!this.sawText) throw new Error('The server returned an empty answer. Please retry.');
        return events;
    }
}

/** Keep UTF-8 and control-frame boundaries independent from HTTP chunking. */
export async function* readChatResponse(response) {
    if (!response.ok) throw new Error(`The answer service returned HTTP ${response.status}. Please retry.`);
    if (!response.body) throw new Error(BAD_RESPONSE);
    const parser = new ChatTransport(response.headers.get('content-type') || '');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let complete = false;
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            for (const event of parser.push(decoder.decode(value, { stream: true }))) yield event;
        }
        for (const event of parser.push(decoder.decode())) yield event;
        for (const event of parser.finish()) yield event;
        complete = true;
    } finally {
        if (!complete) await reader.cancel().catch(() => {});
        reader.releaseLock();
    }
}