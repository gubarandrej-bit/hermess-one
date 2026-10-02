import React, { useState } from 'react';

function App() {
  const [files, setFiles] = useState([]);
  const [logs, setLogs] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const startAnalysis = async () => {
    setIsAnalyzing(true);
    setLogs(["[INFO] Анализ запущен..."]);
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    try {
      const res = await fetch('http://localhost:8000/analyze', { method: 'POST', body: formData });
      const data = await res.json();
      setLogs(prev => [...prev, ...data.findings]);
    } catch (e) {
      setLogs(prev => [...prev, "[ERROR] Ошибка сервера"]);
    }
    setIsAnalyzing(false);
  };

  return (
    <div style={{ backgroundColor: '#121212', color: 'white', minHeight: '100vh', padding: '20px' }}>
      <h1>Hermess-One</h1>
      <input type="file" multiple onChange={e => setFiles(Array.from(e.target.files))} />
      <button onClick={startAnalysis} disabled={isAnalyzing}>Проверить</button>
      <div style={{ background: '#000', color: '#0f0', padding: '10px', marginTop: '20px', fontFamily: 'monospace' }}>
        {logs.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </div>
  );
}
export default App;
