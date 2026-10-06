/* Restored procedural Three.js galaxy from the original library scene. */
(() => {
    if (!window.THREE || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let fpScene, fpCamera, fpRenderer, fpInstancedMesh;
    const FP_PARTICLE_COUNT = 14000;
    let fpClock = new THREE.Clock();
    let fpMouseX = 0, fpMouseY = 0;
    let fpScrollY = window.scrollY || 0;
        function initFullPage3D() {
            const canvas = document.querySelector('[data-archipelago-scene]');
            if (!canvas) return;

            fpScene = new THREE.Scene();
            fpScene.fog = new THREE.FogExp2(0x000000, 0.008);

            fpCamera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1500);
            fpCamera.position.set(0, 0, 95);

            fpRenderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
            fpRenderer.setSize(window.innerWidth, window.innerHeight);
            fpRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));

            const geom = new THREE.TetrahedronGeometry(0.32);
            const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
            fpInstancedMesh = new THREE.InstancedMesh(geom, mat, FP_PARTICLE_COUNT);
            fpInstancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            fpScene.add(fpInstancedMesh);

            const dummy = new THREE.Object3D();
            const color = new THREE.Color();

            for (let i = 0; i < FP_PARTICLE_COUNT; i++) {
                const arm = i % 3;
                const armOffset = (arm * Math.PI * 2) / 3;
                const radius = Math.pow(Math.random(), 0.6) * 75;
                const angle = radius * 0.18 + armOffset + (Math.random() - 0.5) * 0.45;
                const heightSpread = (Math.random() - 0.5) * (20 + (75 - radius) * 0.35);

                const x = Math.cos(angle) * radius;
                const y = heightSpread;
                const z = Math.sin(angle) * radius;

                dummy.position.set(x, y, z);
                dummy.scale.setScalar(0.2 + Math.random() * 0.9);
                dummy.updateMatrix();
                fpInstancedMesh.setMatrixAt(i, dummy.matrix);

                const hue = 0.55 + Math.random() * 0.35;
                color.setHSL(hue, 0.85, 0.65);
                fpInstancedMesh.setColorAt(i, color);
            }
            fpInstancedMesh.instanceMatrix.needsUpdate = true;
            if (fpInstancedMesh.instanceColor) fpInstancedMesh.instanceColor.needsUpdate = true;

            window.addEventListener('mousemove', (e) => {
                fpMouseX = (e.clientX / window.innerWidth - 0.5) * 2;
                fpMouseY = (e.clientY / window.innerHeight - 0.5) * 2;
            }, { passive: true });

            window.addEventListener('scroll', () => {
                fpScrollY = window.scrollY || 0;
            }, { passive: true });

            window.addEventListener('resize', () => {
                fpCamera.aspect = window.innerWidth / window.innerHeight;
                fpCamera.updateProjectionMatrix();
                fpRenderer.setSize(window.innerWidth, window.innerHeight);
            });

            function animateFP() {
                requestAnimationFrame(animateFP);
                const elapsedTime = fpClock.getElapsedTime();

                fpInstancedMesh.rotation.y = elapsedTime * 0.045;
                fpInstancedMesh.rotation.x = Math.sin(elapsedTime * 0.02) * 0.08;

                const targetX = fpMouseX * 22;
                const targetY = -fpMouseY * 16 - (fpScrollY * 0.04);
                const targetZ = 95 + Math.sin(elapsedTime * 0.2) * 4;

                fpCamera.position.x += (targetX - fpCamera.position.x) * 0.04;
                fpCamera.position.y += (targetY - fpCamera.position.y) * 0.04;
                fpCamera.position.z += (targetZ - fpCamera.position.z) * 0.04;
                fpCamera.lookAt(0, -fpScrollY * 0.025, 0);

                fpRenderer.render(fpScene, fpCamera);
            }
            animateFP();
        }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFullPage3D, { once: true });
    } else {
        initFullPage3D();
    }
})();
