import { LuFileSearch, LuScale, LuSearch } from "react-icons/lu";
import "./Features.css";

const STEPS = [
  {
    icon: LuSearch,
    title: "Searches the web",
    description:
      "Your description goes to live search, and we read the comparison articles developers actually use.",
  },
  {
    icon: LuFileSearch,
    title: "Reads each tool's own pages",
    description:
      "For every tool, we read its official site and pricing page, and check licenses and activity on GitHub.",
  },
  {
    icon: LuScale,
    title: "Compares what it can prove",
    description:
      "You get a side-by-side comparison with every source linked. Anything we couldn't confirm stays blank.",
  },
];

const Features = () => (
  <section id="features" className="features-section section">
    <div className="container">
      <p className="section-eyebrow">How it works</p>
      <h2 className="section-title">Answers you can check</h2>
      <p className="section-lead">
        Each search takes about 20 seconds and shows its work, so you can trust the comparison
        or click through and verify it yourself.
      </p>

      <ol className="steps">
        {STEPS.map(({ icon: Icon, title, description }, index) => (
          <li key={title} className="step">
            <div className="step-icon">
              <Icon size={20} aria-hidden="true" />
            </div>
            <p className="step-number">Step {index + 1}</p>
            <h3>{title}</h3>
            <p className="step-description">{description}</p>
          </li>
        ))}
      </ol>
    </div>
  </section>
);

export default Features;
