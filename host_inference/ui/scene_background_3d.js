/* Smooth, animated Three.js vortex for the chat workspace. */
(() => {
    if (!window.THREE || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const canvas = document.querySelector('[data-archipelago-scene]');
    if (!canvas) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.1, 500);
    camera.position.set(0, 0, 94);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.setSize(innerWidth, innerHeight);

    const vortex = new THREE.Group();
    const colors = [0x9b5cff, 0x04c9d7, 0xeb3ed7, 0x6866ff];
    const arms = 6;
    for (let arm = 0; arm < arms; arm++) {
        const points = [];
        for (let step = 0; step <= 90; step++) {
            const progress = step / 90;
            const radius = 3 + progress * 70;
            const angle = progress * Math.PI * 3.5 + arm * Math.PI * 2 / arms;
            points.push(new THREE.Vector3(
                Math.cos(angle) * radius,
                Math.sin(angle) * radius * 0.7,
                -28 + progress * 24
            ));
        }
        const curve = new THREE.CatmullRomCurve3(points);
        const geometry = new THREE.TubeGeometry(curve, 220, arm % 2 ? 0.24 : 0.38, 6, false);
        const material = new THREE.MeshBasicMaterial({
            color: colors[arm % colors.length],
            transparent: true,
            opacity: arm % 2 ? 0.42 : 0.6,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
        vortex.add(new THREE.Mesh(geometry, material));
    }
    for (let ring = 0; ring < 5; ring++) {
        const mesh = new THREE.Mesh(
            new THREE.TorusGeometry(8 + ring * 10, 0.13, 6, 120),
            new THREE.MeshBasicMaterial({
                color: colors[ring % colors.length], transparent: true,
                opacity: 0.26, depthWrite: false, blending: THREE.AdditiveBlending
            })
        );
        mesh.scale.y = 0.68;
        mesh.position.z = -20 - ring * 2;
        vortex.add(mesh);
    }
    scene.add(vortex);

    let pointerX = 0;
    let pointerY = 0;
    addEventListener('pointermove', event => {
        pointerX = event.clientX / innerWidth - 0.5;
        pointerY = event.clientY / innerHeight - 0.5;
    }, { passive: true });
    addEventListener('resize', () => {
        camera.aspect = innerWidth / innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(innerWidth, innerHeight);
    });
    const clock = new THREE.Clock();
    function animate() {
        requestAnimationFrame(animate);
        vortex.rotation.z = clock.getElapsedTime() * 0.045;
        vortex.rotation.x += ((pointerY * 0.16) - vortex.rotation.x) * 0.025;
        vortex.rotation.y += ((pointerX * 0.16) - vortex.rotation.y) * 0.025;
        renderer.render(scene, camera);
    }
    animate();
})();
