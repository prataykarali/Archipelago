// 3D Interactive Opening Book Showcase Engine - Archipelago Central Repository
(function() {
  'use strict';

  let container, scene, camera, renderer, controls;
  let booksData = [];
  let bookInstances = [];
  let activeIndex = 0;
  let onSelectCallback = null;
  let animFrameId = null;
  let isDetailMode = false;
  let selectedBook = null;

  class Spring {
    constructor(v, k = 120, d = 14) {
      this.v = v;
      this.t = v;
      this.vel = 0;
      this.k = k;
      this.d = d;
    }
    set(v) {
      this.v = v;
      this.t = v;
      this.vel = 0;
      return this;
    }
    update(dt) {
      const a = this.k * (this.t - this.v) - this.d * this.vel;
      this.vel += a * dt;
      this.v += this.vel * dt;
      return this.v;
    }
  }

  function createCoverCanvas(title, author, year, primaryColor, accentColor, domain) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 768;
    const ctx = canvas.getContext('2d');

    const grad = ctx.createLinearGradient(0, 0, 512, 768);
    grad.addColorStop(0, primaryColor || '#1e293b');
    grad.addColorStop(1, '#090d16');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 512, 768);

    ctx.strokeStyle = accentColor || '#3b82f6';
    ctx.lineWidth = 12;
    ctx.strokeRect(24, 24, 464, 720);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 4;
    ctx.strokeRect(36, 36, 440, 696);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.font = 'bold 16px sans-serif';
    ctx.fillText((domain || 'ARCHIPELAGO CORPUS EDITION').toUpperCase(), 60, 80);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 34px sans-serif';
    
    const words = (title || 'Knowledge Volume').split(' ');
    let line = '';
    let y = 220;
    for (let i = 0; i < words.length; i++) {
      let testLine = line + words[i] + ' ';
      let metrics = ctx.measureText(testLine);
      if (metrics.width > 400 && i > 0) {
        ctx.fillText(line, 60, y);
        line = words[i] + ' ';
        y += 44;
      } else {
        line = testLine;
      }
    }
    ctx.fillText(line, 60, y);

    ctx.fillStyle = accentColor || '#60a5fa';
    ctx.font = '22px sans-serif';
    ctx.fillText(author || 'Central Repository', 60, y + 55);

    if (year) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.fillRect(60, y + 95, 100, 36);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 18px sans-serif';
      ctx.fillText(year, 80, y + 119);
    }

    ctx.beginPath();
    ctx.arc(256, 580, 50, 0, Math.PI * 2);
    ctx.lineWidth = 6;
    ctx.strokeStyle = accentColor || '#60a5fa';
    ctx.stroke();

    return canvas;
  }

  function createSpineCanvas(title, primaryColor, accentColor) {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 768;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = primaryColor || '#1e293b';
    ctx.fillRect(0, 0, 128, 768);

    ctx.strokeStyle = accentColor || '#3b82f6';
    ctx.lineWidth = 6;
    ctx.strokeRect(8, 8, 112, 752);

    ctx.save();
    ctx.translate(64, 384);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 24px sans-serif';
    ctx.textAlign = 'center';
    const displayTitle = (title || 'ARCHIPELAGO').slice(0, 26);
    ctx.fillText(displayTitle, 0, 8);
    ctx.restore();

    return canvas;
  }

  function createIndexPageCanvas(chapters) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 768;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#f4efdf';
    ctx.fillRect(0, 0, 512, 768);

    ctx.fillStyle = '#2f2a23';
    ctx.textAlign = 'center';
    ctx.font = 'bold 36px Georgia';
    ctx.fillText('TABLE OF CONTENTS', 256, 80);

    ctx.fillStyle = 'rgba(47, 42, 35, 0.2)';
    ctx.fillRect(80, 100, 352, 2);

    const list = chapters && chapters.length ? chapters : [
      { title: 'Chapter 1: Overview & Scope', page: 1 },
      { title: 'Chapter 2: Methods & Formulation', page: 35 },
      { title: 'Chapter 3: Experimental Results', page: 88 },
      { title: 'Chapter 4: Discussion & Synthesis', page: 142 }
    ];

    ctx.textAlign = 'left';
    ctx.font = '500 20px Georgia';
    let y = 160;
    list.forEach((item, i) => {
      ctx.fillStyle = '#2f2a23';
      const itemTitle = typeof item === 'string' ? item : item.title;
      const itemPage = typeof item === 'string' ? (15 * (i + 1)) : item.page;
      ctx.fillText(`${i + 1}. ${itemTitle.slice(0, 28)}`, 80, y);

      ctx.textAlign = 'right';
      ctx.fillStyle = '#6b5c4d';
      ctx.fillText(`p. ${itemPage}`, 432, y);
      ctx.textAlign = 'left';

      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.fillRect(80, y + 12, 352, 1);
      y += 50;
    });

    return canvas;
  }

  function buildBookInstance(book, index) {
    const root = new THREE.Group();
    const floatGroup = new THREE.Group();
    root.add(floatGroup);

    const W = 2.4, H = 3.4, T = 0.45, CT = 0.04, HINGE_OVERLAP = 0.05;
    const PIVOT_Z = T / 2 + CT / 2;

    const coverCanvas = createCoverCanvas(book.title, book.author || book.authors, book.year, book.primaryColor, book.accentColor, book.domain);
    const spineCanvas = createSpineCanvas(book.title, book.primaryColor, book.accentColor);
    const indexCanvas = createIndexPageCanvas(book.toc);

    const coverTex = new THREE.CanvasTexture(coverCanvas);
    const spineTex = new THREE.CanvasTexture(spineCanvas);
    const indexTex = new THREE.CanvasTexture(indexCanvas);

    const pagesMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.8 });
    const spineMat = new THREE.MeshStandardMaterial({ map: spineTex, roughness: 0.3, metalness: 0.1 });
    const coverMat = new THREE.MeshStandardMaterial({ map: coverTex, roughness: 0.3, metalness: 0.1 });
    const indexMat = new THREE.MeshStandardMaterial({ map: indexTex, roughness: 0.8, side: THREE.DoubleSide });
    const backMat = new THREE.MeshStandardMaterial({ color: book.primaryColor || 0x1e293b, roughness: 0.4 });

    const pivot = new THREE.Group();
    pivot.position.set(-W / 2 - HINGE_OVERLAP, 0, PIVOT_Z);

    const coverGeo = new THREE.BoxGeometry(W, H, CT);
    const frontMesh = new THREE.Mesh(coverGeo, [pagesMat, spineMat, pagesMat, pagesMat, coverMat, indexMat]);
    frontMesh.position.x = W / 2;
    frontMesh.castShadow = frontMesh.receiveShadow = true;
    pivot.add(frontMesh);
    floatGroup.add(pivot);

    const spineGeo = new THREE.BoxGeometry(0.05, H, T + CT);
    const spineMesh = new THREE.Mesh(spineGeo, spineMat);
    spineMesh.position.set(-W / 2 - 0.02, 0, 0);
    spineMesh.castShadow = true;
    floatGroup.add(spineMesh);

    const backMesh = new THREE.Mesh(coverGeo, [pagesMat, spineMat, pagesMat, pagesMat, indexMat, backMat]);
    backMesh.position.set(0, 0, -PIVOT_Z);
    backMesh.castShadow = backMesh.receiveShadow = true;
    floatGroup.add(backMesh);

    const blockGeo = new THREE.BoxGeometry(W - 0.05, H - 0.1, T - 0.04);
    const blockMesh = new THREE.Mesh(blockGeo, pagesMat);
    blockMesh.position.set(0.02, 0, 0);
    blockMesh.castShadow = blockMesh.receiveShadow = true;
    floatGroup.add(blockMesh);

    const PAGE_COUNT = 6;
    const pages = [];
    const pageF = [];
    const pageGeo = new THREE.PlaneGeometry(W - 0.1, H - 0.1);
    for (let i = 0; i < PAGE_COUNT; i++) {
      const pageGroup = new THREE.Group();
      pageGroup.position.set(-W / 2 + 0.03, 0, 0.15 - i * 0.04);
      const pageMesh = new THREE.Mesh(pageGeo, i === 0 ? indexMat : pagesMat);
      pageMesh.position.x = (W - 0.1) / 2;
      pageGroup.add(pageMesh);
      floatGroup.add(pageGroup);
      pages.push(pageGroup);
      pageF.push(0.35 * Math.pow(1 - i / PAGE_COUNT, 2.2));
    }

    const hitGeo = new THREE.BoxGeometry(2.6, 3.6, 1.2);
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    const hit = new THREE.Mesh(hitGeo, hitMat);
    floatGroup.add(hit);

    const springs = {
      px: new Spring(0, 120, 14),
      py: new Spring(0, 120, 14),
      pz: new Spring(0, 120, 14),
      rx: new Spring(0, 120, 14),
      ry: new Spring(0, 120, 14),
      rz: new Spring(0, 120, 14),
      sc: new Spring(1, 120, 14),
      cover: new Spring(0, 90, 12),
    };

    root.userData = { index, book };

    return {
      book,
      index,
      root,
      floatGroup,
      pivot,
      pages,
      pageF,
      hit,
      springs,
      phase: Math.random() * 6.28,
    };
  }

  function calculateSlotTransform(slotIndex, activeIdx, totalCount) {
    if (totalCount === 0) return { x: 0, y: 0, z: -15, rotY: 0, scale: 0.001, visible: false };

    let diff = slotIndex - activeIdx;
    if (diff > totalCount / 2) diff -= totalCount;
    if (diff < -totalCount / 2) diff += totalCount;

    if (Math.abs(diff) > 2) {
      return { x: diff * 8, y: 0, z: -15, rotY: 0, scale: 0.001, visible: false };
    }

    if (diff === 0) {
      return { x: 0, y: 0, z: 0.6, rotY: 0, scale: 1.0, visible: true };
    } else if (diff === -1) {
      return { x: -2.3, y: 0, z: -0.8, rotY: 0.38, scale: 0.82, visible: true };
    } else if (diff === 1) {
      return { x: 2.3, y: 0, z: -0.8, rotY: -0.38, scale: 0.82, visible: true };
    } else if (diff === -2) {
      return { x: -4.2, y: 0, z: -2.2, rotY: 0.6, scale: 0.65, visible: true };
    } else if (diff === 2) {
      return { x: 4.2, y: 0, z: -2.2, rotY: -0.6, scale: 0.65, visible: true };
    }
  }

  function updateCarouselTransforms(dt, t) {
    bookInstances.forEach((bInst, idx) => {
      const s = bInst.springs;
      const isSelected = isDetailMode && selectedBook === bInst;

      if (isDetailMode) {
        if (isSelected) {
          bInst.root.visible = true;
          s.px.t = 0;
          s.py.t = 0;
          s.pz.t = 1.3;
          s.rx.t = 0.04;
          s.ry.t = -0.32;
          s.rz.t = 0.01;
          s.sc.t = 1.1;
          s.cover.t = 0.95; // Cover swings open
        } else {
          // Strictly HIDE ALL OTHER 45 BOOKS when 1 book is open!
          bInst.root.visible = false;
          s.sc.t = 0.00001;
          s.pz.t = -30;
          s.cover.t = 0;
        }
      } else {
        // Normal carousel shelf view
        const transform = calculateSlotTransform(idx, activeIndex, booksData.length);
        bInst.root.visible = transform.visible;
        if (transform.visible) {
          s.px.t = transform.x;
          s.py.t = transform.y;
          s.pz.t = transform.z;
          s.rx.t = 0;
          s.ry.t = transform.rotY;
          s.rz.t = 0;
          s.sc.t = transform.scale;
          s.cover.t = 0; // Cover shut on shelf
        }
      }

      s.px.update(dt);
      s.py.update(dt);
      s.pz.update(dt);
      s.rx.update(dt);
      s.ry.update(dt);
      s.rz.update(dt);
      s.sc.update(dt);
      s.cover.update(dt);

      bInst.root.position.set(s.px.v, s.py.v, s.pz.v);
      bInst.root.rotation.set(s.rx.v, s.ry.v, s.rz.v);
      bInst.root.scale.setScalar(Math.max(s.sc.v, 0.00001));

      // Front Cover Swing Open Rotation
      const ang = s.cover.v;
      bInst.pivot.rotation.y = -ang;

      // Fanning out pages
      bInst.pages.forEach((pGroup, pi) => {
        pGroup.rotation.y = -(ang * bInst.pageF[pi]);
      });

      // Floating animation
      bInst.floatGroup.position.y = Math.sin(t * 0.8 + bInst.phase) * 0.03;
      bInst.floatGroup.rotation.z = Math.cos(t * 0.6 + bInst.phase) * 0.005;
    });
  }

  function rebuildMeshes() {
    if (!scene) return;
    bookInstances.forEach(bInst => scene.remove(bInst.root));
    bookInstances = [];
    booksData.forEach((book, i) => {
      const bInst = buildBookInstance(book, i);
      bookInstances.push(bInst);
      scene.add(bInst.root);
    });
    activeIndex = 0;
    isDetailMode = false;
    selectedBook = null;
    if (booksData.length > 0 && onSelectCallback) {
      onSelectCallback(booksData[0], 0, booksData.length, false);
    }
  }

  function setBooks(newBooks) {
    booksData = newBooks || [];
    rebuildMeshes();
  }

  function openBook(index) {
    if (index >= 0 && index < bookInstances.length) {
      activeIndex = index;
      selectedBook = bookInstances[index];
      isDetailMode = true;
      if (onSelectCallback) onSelectCallback(selectedBook.book, activeIndex, booksData.length, true);
    }
  }

  function closeBook() {
    isDetailMode = false;
    selectedBook = null;
    if (onSelectCallback) onSelectCallback(booksData[activeIndex], activeIndex, booksData.length, false);
  }

  function init(containerId, books, callback) {
    container = document.getElementById(containerId);
    if (!container) return;

    booksData = books && books.length > 0 ? books : [];
    onSelectCallback = callback;

    container.innerHTML = '';
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 400;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 6.2);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.95);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight1.position.set(5, 8, 5);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x93c5fd, 0.6);
    dirLight2.position.set(-5, -2, 4);
    scene.add(dirLight2);

    const pointLight = new THREE.PointLight(0xffffff, 0.8, 20);
    pointLight.position.set(0, 2, 4);
    scene.add(pointLight);

    rebuildMeshes();

    if (window.THREE.OrbitControls) {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.enableZoom = false;
      controls.maxPolarAngle = Math.PI / 2 + 0.1;
      controls.minPolarAngle = Math.PI / 2 - 0.3;
    }

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    renderer.domElement.addEventListener('click', (e) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      // Filter out invisible objects
      const visibleChildren = scene.children.filter(c => c.visible);
      const hits = raycaster.intersectObjects(visibleChildren, true);

      if (hits.length > 0) {
        let obj = hits[0].object;
        while (obj.parent && obj.parent !== scene) {
          obj = obj.parent;
        }
        if (obj.userData && typeof obj.userData.index === 'number') {
          const clickedIdx = obj.userData.index;
          if (isDetailMode) {
            if (activeIndex === clickedIdx) {
              closeBook();
            } else {
              openBook(clickedIdx);
            }
          } else {
            openBook(clickedIdx);
          }
        } else if (isDetailMode) {
          closeBook();
        }
      } else if (isDetailMode) {
        // Tapping background in detail mode closes the book
        closeBook();
      }
    });

    const clock = new THREE.Clock();
    if (animFrameId) cancelAnimationFrame(animFrameId);
    function animate() {
      animFrameId = requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.05);
      const t = clock.getElapsedTime();
      updateCarouselTransforms(dt, t);
      if (controls) controls.update();
      renderer.render(scene, camera);
    }
    animate();

    const resizeObserver = new ResizeObserver(() => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w > 0 && h > 0) {
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      }
    });
    resizeObserver.observe(container);
  }

  function selectBookIndex(index) {
    if (isDetailMode) {
      if (activeIndex === index) {
        closeBook();
      } else {
        openBook(index);
      }
    } else {
      activeIndex = index;
      if (onSelectCallback) onSelectCallback(booksData[activeIndex], activeIndex, booksData.length, false);
    }
  }

  window.LibraryShowcase3D = {
    init,
    setBooks,
    selectBookIndex,
    openBook,
    closeBook
  };
})();
