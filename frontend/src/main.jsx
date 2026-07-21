import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// No <StrictMode>: it double-invokes effects in dev, which here means
// double-connecting to LiveKit and requesting the camera/mic twice on every
// mount — visible flicker for a demo that's all about the WebRTC session.
createRoot(document.getElementById('root')).render(<App />)
