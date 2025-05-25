import express, { type Express, Request, Response, NextFunction } from "express";
import { createServer, type Server } from "http";
import axios from "axios";
import { log } from "./vite";

// FastAPI backend URL
const BACKEND_URL = "http://127.0.0.1:8000";

export async function registerRoutes(app: Express): Promise<Server> {
  const apiRouter = express.Router();
  
  // Middleware to handle CORS
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    next();
  });

  // Proxy all API requests to FastAPI backend
  apiRouter.all("*", async (req: Request, res: Response) => {
    try {
      // Build the target URL by combining the backend URL with the original path
      const targetUrl = `${BACKEND_URL}${req.originalUrl.replace(/^\/api/, '')}`;
      log(`Proxying request to: ${targetUrl}`, "express-proxy");
      
      // Forward the request to the FastAPI backend
      const response = await axios({
        method: req.method,
        url: targetUrl,
        data: req.method !== "GET" ? req.body : undefined,
        params: req.method === "GET" ? req.query : undefined,
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        validateStatus: () => true // Accept any status code
      });
      
      // Send the response back to the client
      res.status(response.status).json(response.data);
    } catch (error) {
      console.error("Error proxying request to FastAPI backend:", error);
      
      // Return a specific error message if the FastAPI server is unreachable
      if (axios.isAxiosError(error) && !error.response) {
        return res.status(503).json({
          message: "Unable to connect to the search server. Please make sure the FastAPI backend is running at http://127.0.0.1:8000."
        });
      }
      
      // Generic error response
      res.status(500).json({ 
        message: "An error occurred while processing your request",
        error: error instanceof Error ? error.message : "Unknown error" 
      });
    }
  });
  
  // Register API proxy route
  app.use("/api", apiRouter);

  const httpServer = createServer(app);
  return httpServer;
}
