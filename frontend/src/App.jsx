import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage.jsx";
import BroadcastPage from "./pages/BroadcastPage.jsx";
import WatchPage from "./pages/WatchPage.jsx";
import RecordingsPage from "./pages/RecordingsPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/broadcast" element={<BroadcastPage />} />
        <Route path="/watch" element={<WatchPage />} />
        <Route path="/recordings" element={<RecordingsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
