import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage.jsx";
import BroadcastPage from "./pages/BroadcastPage.jsx";
import WatchPage from "./pages/WatchPage.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/broadcast" element={<BroadcastPage />} />
        <Route path="/watch" element={<WatchPage />} />
      </Routes>
    </BrowserRouter>
  );
}
