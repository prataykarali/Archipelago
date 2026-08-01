/**
 * Chromatic Waves (Originkit DottedBg2) — vanilla OGL port for Archipelago chat.
 * Renders an animated perlin → dotted palette field behind the welcome screen.
 */
import {
  Renderer,
  Camera,
  Mesh,
  Plane,
  Program,
  RenderTarget as OglRenderTarget,
} from "https://esm.sh/ogl@1.0.11";

const MAX_DPR = 2;
const FRAME_INTERVAL_MS = 1000 / 30;
const MAX_COLORS = 10;
const DEFAULT_COLORS = ["#c4a0ff", "#ffffff", "#a78bfa"];
const DEFAULT_BG = "#090514";
const DEFAULT_FREQUENCY = 1.4;
const DEFAULT_SPEED = 4;
const DEFAULT_CELL_SIZE = 34;
const DEFAULT_GAMMA = 6;
const DEFAULT_PALETTE_BIAS = -3;
const UI_FREQ_MIN = 1;
const UI_FREQ_MAX = 10;
const SHADER_FREQ_MIN = 0.3;
const SHADER_FREQ_MAX = 6;
const UI_CELL_MIN = 1;
const UI_CELL_MAX = 100;
const SHADER_CELL_MIN = 6;
const SHADER_CELL_MAX = 60;
const UI_GAMMA_MIN = 1;
const UI_GAMMA_MAX = 20;
const SHADER_GAMMA_MIN = 0.5;
const SHADER_GAMMA_MAX = 8;
const SPEED_SCALE = 0.05;
const BIAS_SCALE = 0.05;
const BG_ELEMENT_ID = "chromatic-waves-bg";

const PERLIN_VERTEX = `#version 300 es
in vec2 uv;
in vec2 position;
out vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0., 1.);
}`;

const PERLIN_FRAGMENT = `#version 300 es
precision mediump float;
uniform float uFrequency;
uniform float uTime;
uniform float uSpeed;
uniform float uValue;
uniform vec2 uResolution;
in vec2 vUv;
out vec4 fragColor;

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2  C = vec2(1.0/6.0, 1.0/3.0);
  const vec4  D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3  ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / max(uResolution.y, 1.0);
  uv = (uv - 0.5) * vec2(aspect, 1.0) + 0.5;
  float hue = abs(snoise(vec3(uv * uFrequency, uTime * uSpeed)));
  vec3 rainbowColor = hsv2rgb(vec3(hue, 1.0, uValue));
  fragColor = vec4(rainbowColor, 1.0);
}`;

const DOT_VERTEX = `#version 300 es
in vec2 uv;
in vec2 position;
out vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0., 1.);
}`;

const DOT_FRAGMENT = `#version 300 es
precision highp float;
uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform int uPaletteCount;
uniform vec3 uPalette[10];
uniform float uPaletteAlpha[10];
uniform float uCellSize;
uniform float uGamma;
uniform float uPaletteBias;
out vec4 fragColor;

void main() {
  vec2 pix = gl_FragCoord.xy;
  float cell = max(uCellSize, 1.0);
  vec2 cellIdx = floor(pix / cell);
  vec2 cellCenter = (cellIdx + 0.5) * cell;
  vec3 col = texture(uTexture, cellCenter / uResolution.xy).rgb;
  float gray = 0.3 * col.r + 0.59 * col.g + 0.11 * col.b;
  gray = pow(clamp(gray, 0.0001, 1.0), uGamma);
  vec2 cellUV = fract(pix / cell) - 0.5;
  float dist = length(cellUV);
  float radius = clamp(gray + uPaletteBias, 0.0, 1.0) * 0.5;
  float aa = fwidth(dist) + 1e-4;
  float mark = 1.0 - smoothstep(radius - aa, radius + aa, dist);
  float g2 = clamp(gray + uPaletteBias, 0.0, 1.0);
  int cnt = max(uPaletteCount, 1);
  vec3 dotCol;
  float dotOpacity;
  if (cnt <= 1) {
    dotCol = uPalette[0];
    dotOpacity = uPaletteAlpha[0];
  } else {
    float scaled = g2 * float(cnt - 1);
    int seg = int(floor(scaled));
    seg = clamp(seg, 0, cnt - 2);
    float f = clamp(scaled - float(seg), 0.0, 1.0);
    dotCol = mix(uPalette[seg], uPalette[seg + 1], f);
    dotOpacity = mix(uPaletteAlpha[seg], uPaletteAlpha[seg + 1], f);
  }
  fragColor = vec4(dotCol, mark * dotOpacity);
}`;

function mapLinear(value, inMin, inMax, outMin, outMax) {
  if (inMax === inMin) return outMin;
  const t = (value - inMin) / (inMax - inMin);
  return outMin + t * (outMax - outMin);
}

function mapFrequencyUiToShader(ui) {
  return mapLinear(ui, UI_FREQ_MIN, UI_FREQ_MAX, SHADER_FREQ_MIN, SHADER_FREQ_MAX);
}

function mapSpeedUiToShader(ui) {
  return ui * SPEED_SCALE;
}

function mapCellSizeUiToShader(ui) {
  return mapLinear(ui, UI_CELL_MIN, UI_CELL_MAX, SHADER_CELL_MIN, SHADER_CELL_MAX);
}

function mapGammaUiToShader(ui) {
  return mapLinear(ui, UI_GAMMA_MIN, UI_GAMMA_MAX, SHADER_GAMMA_MIN, SHADER_GAMMA_MAX);
}

function mapPaletteBiasUiToShader(ui) {
  return ui * BIAS_SCALE;
}

function parseColorToRgba(input) {
  if (!input) return { r: 0, g: 0, b: 0, a: 1 };
  const str = String(input).trim();
  const rgbaMatch = str.match(
    /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)/i
  );
  if (rgbaMatch) {
    return {
      r: Math.max(0, Math.min(255, parseFloat(rgbaMatch[1]))) / 255,
      g: Math.max(0, Math.min(255, parseFloat(rgbaMatch[2]))) / 255,
      b: Math.max(0, Math.min(255, parseFloat(rgbaMatch[3]))) / 255,
      a: rgbaMatch[4] !== undefined
        ? Math.max(0, Math.min(1, parseFloat(rgbaMatch[4])))
        : 1,
    };
  }
  const hex = str.replace(/^#/, "");
  if (hex.length === 8) {
    return {
      r: parseInt(hex.slice(0, 2), 16) / 255,
      g: parseInt(hex.slice(2, 4), 16) / 255,
      b: parseInt(hex.slice(4, 6), 16) / 255,
      a: parseInt(hex.slice(6, 8), 16) / 255,
    };
  }
  if (hex.length === 6) {
    return {
      r: parseInt(hex.slice(0, 2), 16) / 255,
      g: parseInt(hex.slice(2, 4), 16) / 255,
      b: parseInt(hex.slice(4, 6), 16) / 255,
      a: 1,
    };
  }
  if (hex.length === 3) {
    return {
      r: parseInt(hex[0] + hex[0], 16) / 255,
      g: parseInt(hex[1] + hex[1], 16) / 255,
      b: parseInt(hex[2] + hex[2], 16) / 255,
      a: 1,
    };
  }
  return { r: 0, g: 0, b: 0, a: 1 };
}

function buildPaletteUniforms(colorList) {
  const rgb = [];
  const alpha = [];
  for (let i = 0; i < MAX_COLORS; i++) {
    const src = colorList[i];
    if (src != null) {
      const { r, g, b, a } = parseColorToRgba(src);
      rgb.push([r, g, b]);
      alpha.push(a);
    } else {
      rgb.push([0, 0, 0]);
      alpha.push(0);
    }
  }
  return { rgb, alpha };
}

/** @type {{ destroy: () => void, el: HTMLElement } | null} */
let activeInstance = null;

/**
 * Mount Chromatic Waves as a full-bleed background inside a host element.
 * Stays alive for the lifetime of the host (does not tie to welcome).
 * @param {HTMLElement} hostEl  e.g. #chat-stage or #chat-main
 * @param {object} [options]
 * @returns {{ destroy: () => void, el: HTMLElement } | null}
 */
export function mountChromaticWaves(hostEl, options = {}) {
  if (!hostEl) return null;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return null;
  }

  // Already mounted on this host — keep running
  const existing = document.getElementById(BG_ELEMENT_ID);
  if (
    activeInstance &&
    existing &&
    existing.parentElement === hostEl &&
    document.body.contains(existing)
  ) {
    return activeInstance;
  }

  destroyChromaticWaves();

  const frequency = options.frequency ?? DEFAULT_FREQUENCY;
  const speed = options.speed ?? DEFAULT_SPEED;
  const bgColor = options.bgColor ?? DEFAULT_BG;
  const colors =
    Array.isArray(options.colors) && options.colors.length > 0
      ? options.colors
      : DEFAULT_COLORS;
  const cellSize = options.cellSize ?? DEFAULT_CELL_SIZE;
  const gamma = options.gamma ?? DEFAULT_GAMMA;
  const paletteBias = options.paletteBias ?? DEFAULT_PALETTE_BIAS;
  const paletteColors = colors.slice(0, MAX_COLORS);
  const paletteCount = Math.min(MAX_COLORS, Math.max(1, paletteColors.length));
  const palette = buildPaletteUniforms(paletteColors);

  // Ensure host can position absolute children
  const hostStyle = window.getComputedStyle(hostEl);
  if (hostStyle.position === "static") {
    hostEl.style.position = "relative";
  }

  const bgEl = document.createElement("div");
  bgEl.id = BG_ELEMENT_ID;
  bgEl.setAttribute("aria-hidden", "true");
  bgEl.style.background = bgColor;
  // First child so it sits under all stage content
  hostEl.insertBefore(bgEl, hostEl.firstChild);

  const container = document.createElement("div");
  container.style.cssText = "position:absolute;inset:0;width:100%;height:100%;";
  bgEl.appendChild(container);

  let renderer;
  let gl;
  let camera;
  let perlinProgram;
  let dotProgram;
  let perlinMesh;
  let dotMesh;
  let renderTarget;
  let rafId = null;
  let lastTime = 0;
  let isPlaying = true;
  let resizeObserver = null;
  let destroyed = false;

  try {
    renderer = new Renderer({
      dpr: Math.min(window.devicePixelRatio || 1, MAX_DPR),
      alpha: true,
      premultipliedAlpha: false,
    });
    gl = renderer.gl;
    gl.canvas.style.cssText =
      "display:block;width:100%;height:100%;position:absolute;inset:0;";
    container.appendChild(gl.canvas);

    camera = new Camera(gl, { near: 0.1, far: 100 });
    camera.position.set(0, 0, 3);

    perlinProgram = new Program(gl, {
      vertex: PERLIN_VERTEX,
      fragment: PERLIN_FRAGMENT,
      uniforms: {
        uTime: { value: 0 },
        uFrequency: { value: mapFrequencyUiToShader(frequency) },
        uSpeed: { value: mapSpeedUiToShader(speed) },
        uValue: { value: 1 },
        uResolution: { value: [1, 1] },
      },
    });
    perlinMesh = new Mesh(gl, {
      geometry: new Plane(gl, { width: 2, height: 2 }),
      program: perlinProgram,
    });

    renderTarget = new OglRenderTarget(gl);

    dotProgram = new Program(gl, {
      vertex: DOT_VERTEX,
      fragment: DOT_FRAGMENT,
      uniforms: {
        uResolution: { value: [1, 1] },
        uTexture: { value: renderTarget.texture },
        uPaletteCount: { value: paletteCount },
        uPalette: { value: palette.rgb },
        uPaletteAlpha: { value: palette.alpha },
        uCellSize: { value: mapCellSizeUiToShader(cellSize) },
        uGamma: { value: mapGammaUiToShader(gamma) },
        uPaletteBias: { value: mapPaletteBiasUiToShader(paletteBias) },
      },
      transparent: true,
    });
    dotMesh = new Mesh(gl, {
      geometry: new Plane(gl, { width: 2, height: 2 }),
      program: dotProgram,
    });
  } catch (err) {
    console.warn("[chromatic-waves] WebGL init failed:", err);
    bgEl.remove();
    return null;
  }

  const doResize = () => {
    if (destroyed || !renderer || !gl) return;
    const width = Math.max(1, container.clientWidth || bgEl.clientWidth || hostEl.clientWidth || 1);
    const height = Math.max(1, container.clientHeight || bgEl.clientHeight || hostEl.clientHeight || 1);
    renderer.setSize(width, height);
    camera.perspective({ aspect: gl.canvas.width / Math.max(gl.canvas.height, 1) });
    if (renderTarget && renderTarget.setSize) {
      renderTarget.setSize(gl.canvas.width, gl.canvas.height);
    }
    const res = [gl.canvas.width, gl.canvas.height];
    perlinProgram.uniforms.uResolution.value = res;
    dotProgram.uniforms.uResolution.value = res;
  };

  let resizePending = false;
  const scheduleResize = () => {
    if (resizePending || destroyed) return;
    resizePending = true;
    requestAnimationFrame(() => {
      resizePending = false;
      doResize();
      if (!isPlaying) renderOnce();
    });
  };

  const renderOnce = () => {
    if (destroyed || !renderer) return;
    renderer.render({ scene: perlinMesh, camera, target: renderTarget });
    dotProgram.uniforms.uResolution.value = [gl.canvas.width, gl.canvas.height];
    renderer.render({ scene: dotMesh, camera });
  };

  const update = (time) => {
    if (!isPlaying || destroyed) {
      rafId = null;
      return;
    }
    if (time - lastTime < FRAME_INTERVAL_MS) {
      rafId = requestAnimationFrame(update);
      return;
    }
    lastTime = time;
    perlinProgram.uniforms.uTime.value = time * 0.001;
    renderer.render({ scene: perlinMesh, camera, target: renderTarget });
    const res = [gl.canvas.width, gl.canvas.height];
    dotProgram.uniforms.uResolution.value = res;
    perlinProgram.uniforms.uResolution.value = res;
    renderer.render({ scene: dotMesh, camera });
    rafId = requestAnimationFrame(update);
  };

  window.addEventListener("resize", scheduleResize);
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(scheduleResize);
    resizeObserver.observe(hostEl);
    resizeObserver.observe(bgEl);
  }

  doResize();
  renderOnce();
  rafId = requestAnimationFrame(update);
  requestAnimationFrame(() => bgEl.classList.add("is-ready"));

  const destroy = () => {
    if (destroyed) return;
    destroyed = true;
    isPlaying = false;
    if (rafId != null) cancelAnimationFrame(rafId);
    rafId = null;
    window.removeEventListener("resize", scheduleResize);
    if (resizeObserver) {
      try {
        resizeObserver.disconnect();
      } catch (_) {
        /* ignore */
      }
      resizeObserver = null;
    }
    if (gl && gl.canvas && gl.canvas.parentElement) {
      gl.canvas.parentElement.removeChild(gl.canvas);
    }
    if (bgEl.parentNode) bgEl.remove();
    if (activeInstance && activeInstance.el === bgEl) {
      activeInstance = null;
    }
  };

  activeInstance = { destroy, el: bgEl };
  return activeInstance;
}

export function destroyChromaticWaves() {
  if (activeInstance) {
    activeInstance.destroy();
    activeInstance = null;
  }
  const leftover = document.getElementById(BG_ELEMENT_ID);
  if (leftover) leftover.remove();
}

/**
 * Mount on the full chat column background (#chat-stage preferred, else #chat-main).
 * Persistent for the whole session — not tied to welcome.
 * @returns {{ destroy: () => void, el: HTMLElement } | null}
 */
export function mountOnChatBackground(options) {
  const host =
    document.getElementById("chat-stage") ||
    document.getElementById("chat-main") ||
    document.querySelector("main.flex-1");
  if (!host) return null;
  return mountChromaticWaves(host, options);
}

// Back-compat alias
export function mountBehindWelcome(options) {
  return mountOnChatBackground(options);
}

// Global bridge for classic (non-module) scripts in index.html
window.mountChromaticWaves = mountChromaticWaves;
window.destroyChromaticWaves = destroyChromaticWaves;
window.mountChromaticWavesBehindWelcome = mountBehindWelcome;
window.mountChromaticWavesOnChat = mountOnChatBackground;
window.CHROMATIC_WAVES_READY = true;
window.dispatchEvent(new CustomEvent("chromatic-waves-ready"));
