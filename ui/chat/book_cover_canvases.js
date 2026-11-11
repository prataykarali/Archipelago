/* Procedural canvas covers for the library showcase. */
(function () {
  "use strict";
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

  window.ArchipelagoBookCovers = { createCoverCanvas, createSpineCanvas, createIndexPageCanvas };
})();
