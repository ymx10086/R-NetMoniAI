import axios from "axios";

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const API_URL = (process.env.REACT_APP_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
const WS_BASE_URL = API_URL.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
const WS_URL = process.env.REACT_APP_WS_URL || `${WS_BASE_URL}/ws`;

export { API_URL, WS_URL };

export const getNodeStatuses = async () => {
  try {
    const response = await axios.get(`${API_URL}/gcstatuses`);
    return response.data;
  } catch (error) {
    console.error("Error fetching node statuses:", error);
    throw error;
  }
};
