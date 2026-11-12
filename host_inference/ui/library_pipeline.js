async function loadLibraryPipeline() {
  const status = document.getElementById('library-pipeline-status');
  try {
    const response = await fetch('/api/research/intake/activity', { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'activity_unavailable');
    const topicList = document.getElementById('library-topic-list');
    const paperList = document.getElementById('library-recent-papers');
    topicList.replaceChildren();
    paperList.replaceChildren();
    const topics = data.topics || [];
    const topicSearch = document.getElementById('library-topic-search');
    const renderTopics = () => {
      topicList.replaceChildren();
      const query = topicSearch.value.trim().toLocaleLowerCase();
      topics.filter(topic => topic.topic.toLocaleLowerCase().includes(query)).forEach(topic => {
      const item = document.createElement('li');
      item.textContent = `${topic.topic} · ${topic.paper_count} papers`;
      topicList.append(item);
      });
      if (!topicList.childElementCount) topicList.textContent = 'No matching topics.';
    };
    topicSearch.oninput = renderTopics;
    renderTopics();
    (data.papers || []).forEach(paper => {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = paper.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = paper.title;
      const source = document.createElement('small');
      const detail = paper.okf_status === 'processed'
        ? `OKF processed · ${paper.verified_fields} verified fields · ${paper.access_state}`
        : 'Metadata and abstract indexed';
      source.textContent = `${paper.source_name} · ${paper.topic} · ${detail}`;
      item.append(link, source);
      paperList.append(item);
    });
    if (!paperList.childElementCount) paperList.textContent = 'No saved papers yet.';
    status.textContent = `${topics.length} indexed topics · updated from the live research store.`;
  } catch (_error) {
    document.getElementById('library-topic-list').textContent = 'Topics temporarily unavailable.';
    document.getElementById('library-recent-papers').textContent = 'Papers temporarily unavailable.';
  }
  try {
    await window.archipelagoAuthReady;
    const response = await fetch('/api/auth/me', { cache: 'no-store' });
    const data = await response.json();
    document.getElementById('pipeline-research-link').hidden = !response.ok ||
      !data.authenticated || !['student', 'faculty', 'librarian', 'administrator'].includes(data.role);
  } catch (_error) {
    document.getElementById('pipeline-research-link').hidden = true;
  }
}
window.addEventListener('load', loadLibraryPipeline);
window.setInterval(loadLibraryPipeline, 60000);
