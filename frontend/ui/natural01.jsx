import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame, extend } from '@react-three/fiber';
import { OrbitControls, Effects } from '@react-three/drei';
import { UnrealBloomPass } from 'three-stdlib';
import * as THREE from 'three';

extend({ UnrealBloomPass });

const ParticleSwarm = () => {
  const meshRef = useRef();
  const count = 20000;
  const speedMult = 1;
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const target = useMemo(() => new THREE.Vector3(), []);
  const pColor = useMemo(() => new THREE.Color(), []);
  const color = pColor; // Alias for user code compatibility
  
  const positions = useMemo(() => {
     const pos = [];
     for(let i=0; i<count; i++) pos.push(new THREE.Vector3((Math.random()-0.5)*100, (Math.random()-0.5)*100, (Math.random()-0.5)*100));
     return pos;
  }, []);

  // Material & Geom
  const material = useMemo(() => new THREE.MeshBasicMaterial({ color: 0xffffff }), []);
  const geometry = useMemo(() => new THREE.TetrahedronGeometry(0.25), []);

  const PARAMS = useMemo(() => ({"scale":118,"gravity":2.207,"rotation":0.4,"pulse":1.41,"distortion":0.36,"galaxies":3.31}), []);
  const addControl = (id, l, min, max, val) => {
      return PARAMS[id] !== undefined ? PARAMS[id] : val;
  };
  const setInfo = () => {};
  const annotate = () => {};

  useFrame((state) => {
    if (!meshRef.current) return;
    const time = state.clock.getElapsedTime() * speedMult;
    const THREE_LIB = THREE;

    if(material.uniforms && material.uniforms.uTime) {
         material.uniforms.uTime.value = time;
    }

    for (let i = 0; i < count; i++) {
        // USER CODE START
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
        // USER CODE END

        positions[i].lerp(target, 0.1);
        dummy.position.copy(positions[i]);
        dummy.updateMatrix();
        meshRef.current.setMatrixAt(i, dummy.matrix);
        meshRef.current.setColorAt(i, pColor);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
    if (meshRef.current.instanceColor) meshRef.current.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[geometry, material, count]} />
  );
};

export default function App() {
  return (
    <div style={{ width: '100vw', height: '100vh', background: '#000' }}>
      <Canvas camera={{ position: [0, 0, 100], fov: 60 }}>
        <fog attach="fog" args={['#000000', 0.01]} />
        <ParticleSwarm />
        <OrbitControls autoRotate={true} />
        <Effects disableGamma>
            <unrealBloomPass threshold={0} strength={1.8} radius={0.4} />
        </Effects>
      </Canvas>
    </div>
  );
}