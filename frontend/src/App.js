import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';
import moment from 'moment';

function App() {
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [activeUser, setActiveUser] = useState(null);
  const [userCode, setUserCode] = useState('');
  const [activeEntries, setActiveEntries] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');
  const userInputRef = useRef(null);

  useEffect(() => {
    // Focus on user input field when component mounts
    if (userInputRef.current) {
      userInputRef.current.focus();
    }
    
    fetchTasks();
    fetchActiveEntries();
    
    // Set up interval to refresh active entries
    const interval = setInterval(() => {
      fetchActiveEntries();
    }, 10000); // Refresh every 10 seconds
    
    return () => clearInterval(interval);
  }, []);

  const fetchTasks = async () => {
    try {
      const response = await axios.get('/api/tasks');
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
      // If no tasks exist, initialize the database
      try {
        await axios.post('/api/initialize');
        // Fetch tasks again after initialization
        const tasksResponse = await axios.get('/api/tasks');
        setTasks(tasksResponse.data);
      } catch (initError) {
        console.error('Error initializing database:', initError);
      }
    }
  };

  const fetchActiveEntries = async () => {
    try {
      const response = await axios.get('/api/time-entries');
      setActiveEntries(response.data);
    } catch (error) {
      console.error('Error fetching active entries:', error);
    }
  };

  const handleUserCodeSubmit = async (e) => {
    e.preventDefault();
    if (!userCode.trim()) return;
    
    try {
      const response = await axios.get(`/api/users/${userCode}`);
      setActiveUser(response.data);
      setSelectedTask(null);
      setUserCode('');
    } catch (error) {
      console.error('Error finding user:', error);
      setErrorMessage('Użytkownik nie znaleziony. Spróbuj ponownie.');
      setTimeout(() => setErrorMessage(''), 3000);
    }
  };

  const handleTaskSelect = async (task) => {
    if (!activeUser) return;
    
    setSelectedTask(task);
    
    // For main tasks without subtasks or "PRZERWA" task, start time tracking immediately
    if (!task.subtasks || task.subtasks.length === 0 || task.name === "PRZERWA") {
      try {
        await axios.post('/api/time-entries', {
          user_id: activeUser.id,
          task_id: task.id
        });
        
        setActiveUser(null);
        setSelectedTask(null);
        setUserCode('');
        
        // Refocus on user input field
        if (userInputRef.current) {
          userInputRef.current.focus();
        }
        
        // Refresh active entries
        fetchActiveEntries();
      } catch (error) {
        console.error('Error starting time entry:', error);
      }
    }
  };

  const handleSubtaskSelect = async (subtask) => {
    if (!activeUser || !selectedTask) return;
    
    try {
      await axios.post('/api/time-entries', {
        user_id: activeUser.id,
        task_id: subtask.id
      });
      
      setActiveUser(null);
      setSelectedTask(null);
      setUserCode('');
      
      // Refocus on user input field
      if (userInputRef.current) {
        userInputRef.current.focus();
      }
      
      // Refresh active entries
      fetchActiveEntries();
    } catch (error) {
      console.error('Error starting time entry:', error);
    }
  };

  const formatTime = (timeString) => {
    return moment(timeString).format('HH:mm:ss');
  };

  const getElapsedTime = (startTime) => {
    const start = moment(startTime);
    const now = moment();
    const duration = moment.duration(now.diff(start));
    
    const hours = Math.floor(duration.asHours());
    const minutes = Math.floor(duration.asMinutes()) % 60;
    const seconds = Math.floor(duration.asSeconds()) % 60;
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="app">
      <header className="header">
        <h1>System rejestracji czasu pracy</h1>
        <form onSubmit={handleUserCodeSubmit} className="user-form">
          <input
            type="text"
            value={userCode}
            onChange={(e) => setUserCode(e.target.value)}
            placeholder="Zeskanuj identyfikator pracownika..."
            className="user-input"
            ref={userInputRef}
            autoFocus
          />
          <button type="submit" className="submit-button">Zaloguj</button>
        </form>
        {errorMessage && <div className="error-message">{errorMessage}</div>}
        {activeUser && (
          <div className="active-user">
            <p>Zalogowany: <strong>{activeUser.name}</strong></p>
          </div>
        )}
      </header>

      <main className="main-content">
        {activeUser && !selectedTask && (
          <div className="task-grid">
            <h2>Wybierz zadanie:</h2>
            <div className="task-cards">
              {tasks.map(task => (
                <div 
                  key={task.id} 
                  className="task-card"
                  onClick={() => handleTaskSelect(task)}
                >
                  {task.name}
                </div>
              ))}
            </div>
          </div>
        )}

        {activeUser && selectedTask && selectedTask.subtasks && selectedTask.subtasks.length > 0 && (
          <div className="subtask-grid">
            <h2>Wybierz podzadanie dla: {selectedTask.name}</h2>
            <div className="task-cards">
              {selectedTask.subtasks.map(subtask => (
                <div 
                  key={subtask.id} 
                  className="task-card subtask-card"
                  onClick={() => handleSubtaskSelect(subtask)}
                >
                  {subtask.name}
                </div>
              ))}
              <div 
                className="task-card back-button"
                onClick={() => setSelectedTask(null)}
              >
                Powrót
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <h3>Aktywne zadania:</h3>
        <div className="active-entries">
          <table>
            <thead>
              <tr>
                <th>Pracownik</th>
                <th>Zadanie</th>
                <th>Podzadanie</th>
                <th>Czas rozpoczęcia</th>
                <th>Czas trwania</th>
              </tr>
            </thead>
            <tbody>
              {activeEntries.map(entry => (
                <tr key={entry.id}>
                  <td>{entry.user.name}</td>
                  <td>{entry.task.parent ? entry.task.parent.name : entry.task.name}</td>
                  <td>{entry.task.parent ? entry.task.name : ''}</td>
                  <td>{formatTime(entry.start_time)}</td>
                  <td>{getElapsedTime(entry.start_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </footer>
    </div>
  );
}

export default App;