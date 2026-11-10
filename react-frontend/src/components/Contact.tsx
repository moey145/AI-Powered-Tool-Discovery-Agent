import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import emailjs from "@emailjs/browser";
import { useToast } from "../contexts/useToast";
import "./Contact.css";

const EMAILJS_PUBLIC_KEY = "O4KLgYM0Xwo4YjNHk";
const MIN_FILL_MS = 3000;
const SUCCESS_MESSAGE = "Thank you! I will get back to you as soon as possible.";
const FAILURE_MESSAGE = "Ahh, something went wrong. Please try again.";

const Contact = () => {
  const addToast = useToast();
  const [form, setForm] = useState({ name: "", email: "", message: "", website: "" });
  const [loading, setLoading] = useState(false);
  const [openedAt] = useState(() => Date.now());

  useEffect(() => {
    emailjs.init(EMAILJS_PUBLIC_KEY);
  }, []);

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // Bots tend to fill every field, including this hidden one, or submit instantly.
    // They get the normal success message so they have no signal to adapt to.
    if (form.website || Date.now() - openedAt < MIN_FILL_MS) {
      addToast(SUCCESS_MESSAGE, "success", 6000);
      return;
    }

    setLoading(true);
    try {
      const result = await emailjs.send(
        "service_olr4c6j",
        "template_ar04l07",
        { name: form.name, email: form.email, message: form.message },
        EMAILJS_PUBLIC_KEY
      );
      if (result.status === 200) {
        addToast(SUCCESS_MESSAGE, "success", 6000);
        setForm({ name: "", email: "", message: "", website: "" });
      } else {
        addToast(FAILURE_MESSAGE, "error");
      }
    } catch {
      addToast(FAILURE_MESSAGE, "error");
    } finally {
      setLoading(false);
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
              <div
                aria-hidden="true"
                style={{ position: "absolute", left: "-9999px", height: 0, overflow: "hidden" }}
              >
                <label htmlFor="website">Website</label>
                <input
                  type="text"
                  id="website"
                  name="website"
                  value={form.website}
                  onChange={handleChange}
                  tabIndex={-1}
                  autoComplete="off"
                />
              </div>

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
                  rows={5}
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
    </div>
  );
};

export default Contact;
