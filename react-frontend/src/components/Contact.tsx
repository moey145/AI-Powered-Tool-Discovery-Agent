import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import emailjs from "@emailjs/browser";
import { LuSend } from "react-icons/lu";
import { useToast } from "../contexts/useToast";
import "./Contact.css";

const EMAILJS_PUBLIC_KEY = "O4KLgYM0Xwo4YjNHk";
const MIN_FILL_MS = 3000;
const SUCCESS_MESSAGE = "Thanks! I'll get back to you as soon as possible.";
const FAILURE_MESSAGE = "Something went wrong sending your message. Please try again.";

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
      addToast(SUCCESS_MESSAGE, "success", 5000);
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
        addToast(SUCCESS_MESSAGE, "success", 5000);
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
    <div className="contact section container">
      <div className="contact-intro">
        <p className="section-eyebrow">Contact</p>
        <h2 className="section-title">Get in touch</h2>
        <p className="section-lead">
          Questions, feedback, or a tool we got wrong? Send a message and I'll reply by email.
        </p>
      </div>

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

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="name">Name</label>
            <input
              className="field"
              type="text"
              id="name"
              name="name"
              value={form.name}
              onChange={handleChange}
              autoComplete="name"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              className="field"
              type="email"
              id="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              required
              disabled={loading}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="message">Message</label>
          <textarea
            className="field"
            id="message"
            name="message"
            rows={5}
            value={form.message}
            onChange={handleChange}
            required
            disabled={loading}
          ></textarea>
        </div>

        <button type="submit" className="btn btn-primary contact-submit" disabled={loading}>
          <LuSend size={16} aria-hidden="true" />
          {loading ? "Sending..." : "Send message"}
        </button>
      </form>
    </div>
  );
};

export default Contact;
