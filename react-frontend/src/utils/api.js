import axios from "axios";

// Use Vercel/Vite env if present; fallback to local dev for preview
const API_BASE_URL =
  import.meta?.env?.VITE_API_BASE_URL || "http://localhost:8000";

export const api = {
  searchTools: async (query) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/research`, { query });
      return response.data;
    } catch (error) {
      // Extract validation error details from the response
      if (error.response?.data?.detail) {
        const errorDetail = error.response.data.detail;

        // Check if it's a validation error (422 status)
        if (error.response.status === 422) {
          // Handle Pydantic validation errors
          if (Array.isArray(errorDetail)) {
            const validationErrors = errorDetail.map((err) => ({
              field: err.loc ? err.loc.join(".") : "query",
              message: err.msg,
              type: "validation",
            }));
            throw new Error(
              JSON.stringify({
                type: "validation",
                errors: validationErrors,
                message: "Please check your input and try again.",
              })
            );
          }
        }

        // Handle other API errors
        throw new Error(
          JSON.stringify({
            type: "api",
            message: errorDetail,
            status: error.response.status,
          })
        );
      }

      // Handle network or other errors
      throw new Error(
        JSON.stringify({
          type: "network",
          message:
            error.message ||
            "Network error. Please check your connection and try again.",
          originalError: error.message,
        })
      );
    }
  },
};
