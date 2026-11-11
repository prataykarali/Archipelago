window.addEventListener('popstate', (e) => {
    const readingModal = document.getElementById('reading-modal');
    if (readingModal && !readingModal.classList.contains('hidden')) {
        closeReadingMode(true);
    }
    const roadmapModal = document.getElementById('roadmap-modal');
    if (roadmapModal && !roadmapModal.classList.contains('hidden')) {
        closeRoadmapModal(true);
    }
    const choiceModal = document.getElementById('graph-choice-modal');
    if (choiceModal && !choiceModal.classList.contains('hidden')) {
        dismissGraphChoiceModal();
    }
});
