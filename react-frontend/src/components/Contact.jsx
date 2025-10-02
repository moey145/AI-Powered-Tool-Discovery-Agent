import React, { useState, useEffect } from "react";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import emailjs from "@emailjs/browser";

import "./Contact.css";

const Contact = () => {
  const [form, setForm] = useState({
    name: "",
    email: "",
    message: "",
  });

  const [loading, setLoading] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Initialize EmailJS
  useEffect(() => {
    emailjs.init("O4KLgYM0Xwo4YjNHk"); // Your EmailJS user ID
  }, []);

  // Detect theme changes
  useEffect(() => {
    const checkTheme = () => {
      const isDark =
        document.documentElement.classList.contains("dark") ||
        document.body.classList.contains("dark");
      setIsDarkMode(isDark);
    };

    checkTheme();
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  const handleChange = (e) => {
    const { target } = e;
    const { name, value } = target;

    setForm({
      ...form,
      [name]: value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await emailjs.send(
        "service_olr4c6j", // Your EmailJS service ID
        "template_ar04l07", // Your EmailJS template ID
        {
          name: form.name,
          email: form.email,
          message: form.message,
        },
        "O4KLgYM0Xwo4YjNHk" // Your EmailJS user ID
      );

      if (result.status === 200) {
        setLoading(false);
        toast.success(
          "Thank you! I will get back to you as soon as possible.",
          {
            position: "top-right",
            autoClose: 6000,
            hideProgressBar: false,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: true,
            theme: isDarkMode ? "dark" : "light",
          }
        );
        setForm({ name: "", email: "", message: "" });
      } else {
        setLoading(false);
        toast.error("Ahh, something went wrong. Please try again.", {
          position: "top-right",
          autoClose: 5000,
          hideProgressBar: false,
          closeOnClick: true,
          pauseOnHover: true,
          draggable: true,
          theme: isDarkMode ? "dark" : "light",
        });
      }
    } catch (error) {
      setLoading(false);
      toast.error("Ahh, something went wrong. Please try again.", {
        position: "top-right",
        autoClose: 5000,
        hideProgressBar: false,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
        theme: isDarkMode ? "dark" : "light",
      });
    }
  };

  return (
    <div className="contact-section">
      <div className="contact-header">
        <h1>Get In Touch</h1>
        <p className="contact-subtitle">Have questions about Tool Scraper?</p>
      </div>

      <div className="contact-container">
        <div className="contact-content">
          <div className="contact-form-container">
            <form onSubmit={handleSubmit} className="contact-form">
              <div className="form-group">
                <label htmlFor="name">Name</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  placeholder="Enter your name"
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="Enter your email"
                  required
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="message">Message</label>
                <textarea
                  id="message"
                  name="message"
                  rows="5"
                  value={form.message}
                  onChange={handleChange}
                  placeholder="Tell us about your experience with Tool Scraper..."
                  required
                  disabled={loading}
                ></textarea>
              </div>

              <button type="submit" className="submit-btn" disabled={loading}>
                {loading ? "Sending..." : "Send Message"}
              </button>
            </form>
          </div>
        </div>
      </div>

      <ToastContainer theme={isDarkMode ? "dark" : "light"} />
    </div>
  );
};

export default Contact;
