import axios from "axios";
export const api = axios.create(); // Vite proxy handles /api -> Flask

export const getHealth = () => api.get("/api/health").then(r => r.data);
export const getHello  = () => api.get("/api/hello").then(r => r.data);
