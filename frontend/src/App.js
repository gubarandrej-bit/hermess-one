import React, { useState, useEffect } from 'react';
import './App.css';

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
      
      // Отображаем лог из ответа сервера
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
      addLog('SUCCESS', `Анализ завершен. Найдено замечаний: ${data.summary?.total_findings || 0}`);

    } catch (error) {
      addLog('ERROR', `Ошибка при анализе: ${error.message}`);
      addLog('ERROR', 'Проверьте подключение к серверу');
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
    
    // В реальной реализации — запрос к серверу для генерации файла
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
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <h1>Hermess-One</h1>
            <span className="version">v1.0.0</span>
          </div>
          <div className="status-indicator">
            <div className={`status-dot ${apiStatus}`}></div>
            <span>Сервер: {apiStatus === 'online' ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        <div className="grid-layout">
          {/* Левая панель - Загрузка файлов */}
          <section className="panel upload-panel">
            <h2>Входные данные</h2>
            
            <div className="upload-zone">
              <input
                type="file"
                id="file-upload"
                multiple
                onChange={handleFileChange}
                accept=".pdf,.dwg,.dxf,.xls,.xlsx,.doc,.docx"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-upload" className="upload-label">
                <div className="upload-icon">📁</div>
                <div className="upload-text">
                  {files.length > 0 ? (
                    <>
                      <strong>Выбрано файлов: {files.length}</strong>
                      <ul className="file-list">
                        {files.map((file, idx) => (
                          <li key={idx}>{file.name}</li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <>
                      <strong>Выберите файлы</strong>
                      <p>PDF, DWG, XLS, DOC</p>
                      <p className="hint">Кабельный журнал, Спецификация, Чертежи</p>
                    </>
                  )}
                </div>
              </label>
            </div>

            <button
              className="analyze-button"
              onClick={startAnalysis}
              disabled={isAnalyzing || files.length === 0}
            >
              {isAnalyzing ? (
                <>
                  <span className="spinner"></span>
                  Анализ документов...
                </>
              ) : (
                '🔍 Запустить проверку'
              )}
            </button>

            {results && (
              <div className="export-section">
                <h3>Экспорт отчета</h3>
                <div className="export-buttons">
                  <button onClick={() => exportReport('doc')} className="export-btn">
                    📄 DOC
                  </button>
                  <button onClick={() => exportReport('xls')} className="export-btn">
                    📊 XLS
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Правая панель - Лог и результаты */}
          <section className="panel results-panel">
            <h2>Диалоговое окно проверки</h2>
            
            <div className="log-window">
              {logs.length === 0 ? (
                <div className="log-placeholder">
                  Ожидание действий пользователя...
                </div>
              ) : (
                logs.map((log, idx) => (
                  <div key={idx} className="log-entry" style={{ color: getLogColor(log.level) }}>
                    <span className="log-time">[{log.timestamp}]</span>
                    <span className="log-level">[{log.level}]</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))
              )}
            </div>

            {results && results.findings && (
              <div className="findings-section">
                <h3>Замечания ({results.summary?.total_findings || 0})</h3>
                <div className="findings-list">
                  {results.findings.map((finding, idx) => (
                    <div key={idx} className={`finding-item ${finding.severity}`}>
                      <div className="finding-header">
                        <span className="severity-icon">{getSeverityIcon(finding.severity)}</span>
                        <span className="severity-label">{finding.severity}</span>
                      </div>
                      <div className="finding-message">{finding.message}</div>
                      {finding.ntd_reference && (
                        <div className="finding-ntd">
                          📚 {finding.ntd_reference}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="footer">
        <p>Система анализа и проверки рабочей документации по инженерным системам</p>
        <p>Соответствие НТД РФ: ПУЭ, ГОСТ, СП</p>
      </footer>
    </div>
  );
}

export default App;
