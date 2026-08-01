import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

export class ParticlesSwarm {
    constructor(container, count = 20000) {
        this.count = count;
        this.container = container;
        this.speedMult = 1;
        
        // SETUP
        this.scene = new THREE.Scene();
        this.scene.fog = new THREE.FogExp2(0x000000, 0.01);
        this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2000);
        this.camera.position.set(0, 0, 100);
        
        this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.container.appendChild(this.renderer.domElement);

        // POST PROCESSING
        this.composer = new EffectComposer(this.renderer);
        this.composer.addPass(new RenderPass(this.scene, this.camera));
        const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.85);
        bloomPass.strength = 1.8; bloomPass.radius = 0.4; bloomPass.threshold = 0;
        this.composer.addPass(bloomPass);

        // OBJECTS
        this.dummy = new THREE.Object3D();
        this.color = new THREE.Color();
        this.target = new THREE.Vector3();
        this.pColor = new THREE.Color();
        
        this.geometry = new THREE.TetrahedronGeometry(0.25);
        this.material = new THREE.MeshBasicMaterial({ color: 0xffffff });
        
        this.mesh = new THREE.InstancedMesh(this.geometry, this.material, this.count);
        this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        this.scene.add(this.mesh);
        
        this.positions = [];
        for(let i=0; i<this.count; i++) {
            this.positions.push(new THREE.Vector3((Math.random()-0.5)*100, (Math.random()-0.5)*100, (Math.random()-0.5)*100));
            this.mesh.setColorAt(i, this.color.setHex(0x00ff88));
        }
        
        this.clock = new THREE.Clock();
        this.animate = this.animate.bind(this);
        this.animate();
    }

    animate() {
        requestAnimationFrame(this.animate);
        const time = this.clock.getElapsedTime() * this.speedMult;
        
        if(this.material.uniforms && this.material.uniforms.uTime) {
            this.material.uniforms.uTime.value = time;
        }

        // API Stubs
        const PARAMS = {"scale":118,"gravity":2.207,"rotation":0.4,"pulse":1.41,"distortion":0.36,"galaxies":3.31};
        const addControl = (id, l, min, max, val) => {
             return PARAMS[id] !== undefined ? PARAMS[id] : val;
        };
        const setInfo = () => {};
        const annotate = () => {};
        let THREE_LIB = THREE;
        
        let THREE_LIB = THREE;
        const count = this.count; // Alias for user code
        
        for(let i=0; i<this.count; i++) {
            let target = this.target;
            let color = this.pColor;
            
            // INJECTED CODE
            const scale = addControl("scale", "Cosmic Scale", 20, 300, 120);
            const gravity = addControl("gravity", "Gravity Strength", 0.1, 5.0, 1.5);
            const rotation = addControl("rotation", "Rotation Velocity", 0.0, 5.0, 1.0);
            const pulse = addControl("pulse", "Energy Pulse", 0.0, 3.0, 1.2);
            const distortion = addControl("distortion", "Dimensional Distortion", 0.0, 2.0, 0.5);
            const galaxies = addControl("galaxies", "Galaxy Count", 1.0, 12.0, 4.0);
            
            const t = time * rotation;
            const p = i / Math.max(count, 1);
            
            const golden = 2.399963229728653;
            const arm = p * galaxies * 6.28318530718;
            const theta = i * golden + t * 0.25;
            
            const radiusBase = Math.sqrt(p) * scale;
            const waveA = Math.sin(theta * 2.0 + t * 0.8);
            const waveB = Math.cos(theta * 3.0 - t * 0.6);
            const waveC = Math.sin(arm * 2.0 + t);
            
            const radius =
            radiusBase *
            (1.0 + 0.25 * waveA + 0.15 * distortion * waveB);
            
            const swirl =
            theta +
            gravity * radius * 0.015 +
            0.5 * waveC;
            
            const x =
            Math.cos(swirl) * radius +
            Math.sin(theta * 4.0 + t) * distortion * radius * 0.15;
            
            const y =
            (radiusBase - scale * 0.5) * 0.8 +
            Math.sin(theta * 1.5 + t * 0.7) * scale * 0.18 +
            waveA * distortion * scale * 0.08;
            
            const z =
            Math.sin(swirl) * radius +
            Math.cos(theta * 5.0 - t) * distortion * radius * 0.15;
            
            target.set(x, y, z);
            
            const energy =
            0.5 +
            0.5 * Math.sin(
            radius * 0.05 -
            t * pulse +
            waveB
            );
            
            const hue =
            0.58 +
            0.18 * Math.sin(theta * 0.15 + t * 0.1) +
            0.08 * energy;
            
            const sat =
            0.75 +
            0.25 * Math.abs(
            Math.sin(theta * 0.5)
            );
            
            const light =
            0.35 +
            0.45 * energy +
            0.15 * Math.abs(waveA);
            
            color.setHSL(
            ((hue % 1) + 1) % 1,
            Math.min(1, sat),
            Math.min(1, light)
            );
            
            if (i === 0) {
            setInfo(
            "Celestial Genesis",
            "A living galaxy engine where streams of stardust orbit a cosmic singularity and evolve through gravitational waves."
            );
            
            annotate(
            "core",
            new THREE.Vector3(0, 0, 0),
            "Core Singularity"
            );
            
            annotate(
            "ring",
            new THREE.Vector3(scale * 0.6, 0, 0),
            "Stellar Ring"
            );
            
            annotate(
            "stream",
            new THREE.Vector3(0, scale * 0.3, scale * 0.6),
            "Energy Stream"
            );
            
            annotate(
            "nexus",
            new THREE.Vector3(-scale * 0.7, 0, 0),
            "Galactic Nexus"
            );
            }
            
            // UPDATE
            this.positions[i].lerp(this.target, 0.1);
            this.dummy.position.copy(this.positions[i]);
            this.dummy.updateMatrix();
            this.mesh.setMatrixAt(i, this.dummy.matrix);
            this.mesh.setColorAt(i, this.pColor);
        }
        this.mesh.instanceMatrix.needsUpdate = true;
        this.mesh.instanceColor.needsUpdate = true;
        
        this.composer.render();
    }
    
    dispose() {
        this.geometry.dispose();
        this.material.dispose();
        this.scene.remove(this.mesh);
        this.renderer.dispose();
    }
}