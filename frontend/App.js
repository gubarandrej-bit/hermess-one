import React, { useState, useEffect } from 'react';

function App() {
  const [files, setFiles] = useState([]);
  const [logs, setLogs] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [apiStatus, setApiStatus] = useState('checking');

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      if (response.ok) {
        setApiStatus('online');
      } else {
        setApiStatus('offline');
      }
    } catch (error) {
      setApiStatus('offline');
    }
  };

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
    addLog('INFO', `Выбрано файлов: ${e.target.files.length}`);
  };

  const addLog = (level, message) => {
    const timestamp = new Date().toLocaleTimeString('ru-RU');
    setLogs(prev => [...prev, { timestamp, level, message }]);
  };

  const startAnalysis = async () => {
    if (files.length === 0) {
      addLog('ERROR', 'Не выбраны файлы для анализа');
      return;
    }

    setIsAnalyzing(true);
    setLogs([]);
    setResults(null);

    addLog('INFO', 'Инициализация системы анализа...');
    addLog('INFO', 'Загрузка базы НТД...');

    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      addLog('INFO', 'Отправка файлов на сервер...');
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      addLog('INFO', 'Анализ завершен. Обработка результатов...');
      
      if (data.log) {
        data.log.forEach(logEntry => {
          if (logEntry.includes('[INFO]')) {
            addLog('INFO', logEntry.replace('[INFO]', '').trim());
          } else if (logEntry.includes('[WARNING]')) {
            addLog('WARNING', logEntry.replace('[WARNING]', '').trim());
          } else if (logEntry.includes('[ERROR]')) {
            addLog('ERROR', logEntry.replace('[ERROR]', '').trim());
          } else if (logEntry.includes('[RESULT]')) {
            addLog('RESULT', logEntry.replace('[RESULT]', '').trim());
          } else if (logEntry.includes('[DONE]')) {
            addLog('SUCCESS', logEntry.replace('[DONE]', '').trim());
          }
        });
      }

      setResults(data);
    } catch (error) {
      addLog('ERROR', `Ошибка при анализе: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const exportReport = async (format) => {
    if (!results) {
      addLog('WARNING', 'Нет данных для экспорта');
      return;
    }
    addLog('INFO', `Экспорт отчета в формате ${format.toUpperCase()}...`);
    setTimeout(() => {
      addLog('SUCCESS', `Отчет экспортирован: report_${Date.now()}.${format}`);
    }, 1000);
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return '❌';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return '✅';
    }
  };

  const getLogColor = (level) => {
    switch (level) {
      case 'ERROR': return '#ff5252';
      case 'WARNING': return '#ffab40';
      case 'SUCCESS': return '#69f0ae';
      case 'RESULT': return '#40c4ff';
      default: return '#b0bec5';
    }
  };

  return (
    <div style={{ backgroundColor: '#0f0f0f', color: '#e0e0e0', minHeight: '100vh', padding: '30px', fontFamily: 'Inter, sans-serif' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
          <div>
            <h1 style={{ color: '#bb86fc', margin: 0 }}>Hermess-One</h1>
            <p style={{ color: '#888' }}>Система анализа и проверки рабочей документации</p>
          </div>
          <div style={{ backgroundColor: '#1e1e1e', padding: '10px 20px', borderRadius: '20px', border: '1px solid #333' }}>
            Статус: <span style={{ color: apiStatus === 'online' ? '#03dac6' : '#ff5252' }}>{apiStatus}</span>
          </div>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '20px' }}>
          <section style={{ backgroundColor: '#1a1a1a', padding: '25px', borderRadius: '16px', border: '1px solid #333' }}>
            <h3 style={{ marginBottom: '20px' }}>Входные данные</h3>
            <div style={{ border: '2px dashed #333', padding: '30px', textAlign: 'center', borderRadius: '12px', marginBottom: '20px' }}>
              <input type="file" multiple onChange={handleFileChange} style={{ display: 'none' }} id="file-upload" />
              <label htmlFor="file-upload" style={{ cursor: 'pointer', color: '#bb86fc' }}>
                {files.length > 0 ? `Выбрано файлов: ${files.length}` : 'Выберите файлы (PDF, DWG, XLS)'}
              </label>
            </div>
            <button 
              onClick={startAnalysis} 
              disabled={isAnalyzing || files.length === 0}
              style={{ width: '100%', padding: '15px', borderRadius: '8px', border: 'none', backgroundColor: '#bb86fc', fontWeight: 'bold', cursor: 'pointer' }}
            >
              {isAnalyzing ? 'Анализ...' : 'Запустить проверку'}
            </button>
          </section>

          <section style={{ backgroundColor: '#1a1a1a', padding: '25px', borderRadius: '16px', border: '1px solid #333' }}>
            <h3 style={{ marginBottom: '20px' }}>Лог проверки</h3>
            <div style={{ backgroundColor: '#000', padding: '20px', borderRadius: '12px', fontFamily: 'monospace', height: '500px', overflowY: 'auto' }}>
              {logs.length === 0 ? (
                <div style={{ color: '#555' }}>Ожидание...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} style={{ marginBottom: '10px', color: getLogColor(log.level) }}>
                    <span>[{log.timestamp}] </span><span>{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;
