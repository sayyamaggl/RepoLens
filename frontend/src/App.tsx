import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import RepoDetailPage from './pages/RepoDetailPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/repo/:id" element={<RepoDetailPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;