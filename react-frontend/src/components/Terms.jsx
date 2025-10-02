import React from "react";
import "./StaticPages.css";

const Terms = () => {
  const backHome = (e) => {
    e.preventDefault();
    if (window.location.pathname !== "/") {
      window.history.pushState({}, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <main className="static-container">
      <a href="/" className="back-home" onClick={backHome}>
        ← Back to Home
      </a>
      <header className="static-header">
        <h1>Terms of Service</h1>
      </header>
      <section className="static-section">
        <p>
          <strong>Last updated: September 2025</strong>
        </p>

        <h2>1. Acceptance of Terms</h2>
        <p>
          By accessing and using Tool Scraper ("the Service"), you accept and
          agree to be bound by these Terms of Use. If you do not agree to these
          terms, please do not use the Service.
        </p>

        <h2>2. Service Description</h2>
        <p>
          Tool Scraper provides AI-powered tool discovery and analysis services,
          including tool research, comparison, and recommendations. The Service
          uses third-party AI services to process and analyze tool information
          and generate comprehensive insights.
        </p>

        <h2>3. No Warranty - Use at Your Own Risk</h2>
        <p>
          <strong>
            THE SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
          </strong>{" "}
          You acknowledge and agree that:
        </p>
        <ul>
          <li>
            The Service is provided without any warranties, express or implied
          </li>
          <li>
            We do not warrant the accuracy, completeness, or reliability of any
            information provided
          </li>
          <li>You use the Service entirely at your own risk</li>
          <li>
            We are not responsible for any decisions made based on information
            from the Service
          </li>
          <li>Tool information may be outdated, incomplete, or inaccurate</li>
        </ul>

        <h2>4. Data Processing and Third-Party Services</h2>
        <p>You acknowledge and agree that:</p>
        <ul>
          <li>
            Your search queries are processed by third-party AI services
            (OpenAI, Google Custom Search API, BeautifulSoup)
          </li>
          <li>We do not store your search queries on our servers</li>
          <li>
            Data is temporarily processed to provide search results and analysis
          </li>
          <li>Third-party services may be located outside Australia</li>
          <li>
            You should not submit confidential or sensitive information in
            search queries
          </li>
        </ul>

        <h2>5. User Responsibilities</h2>
        <p>You agree to:</p>
        <ul>
          <li>Use the Service only for lawful purposes</li>
          <li>
            Not submit confidential, sensitive, or proprietary information in
            search queries
          </li>
          <li>
            Verify any information obtained through the Service independently
          </li>
          <li>Comply with all applicable laws and regulations</li>
          <li>Not attempt to circumvent usage limits or security measures</li>
        </ul>

        <h2>6. Limitation of Liability</h2>
        <p>
          <strong>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE SHALL NOT BE LIABLE FOR
            ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR
            PUNITIVE DAMAGES ARISING FROM YOUR USE OF THE SERVICE, INCLUDING BUT
            NOT LIMITED TO:
          </strong>
        </p>
        <ul>
          <li>Tool selection decisions based on Service information</li>
          <li>Inaccurate or outdated tool information</li>
          <li>Service interruptions or downtime</li>
          <li>Data processing errors</li>
          <li>Any losses or damages whatsoever</li>
        </ul>

        <h2>7. Intellectual Property</h2>
        <p>
          The Service and its original content, features, and functionality are
          owned by Tool Scraper and are protected by international copyright,
          trademark, and other intellectual property laws.
        </p>

        <h2>8. Usage Limits</h2>
        <p>
          We may impose usage limits on the Service. Excessive use may result in
          temporary or permanent suspension of access. For higher volume
          requirements, please contact us for enterprise solutions.
        </p>

        <h2>9. Modifications to Terms</h2>
        <p>
          We reserve the right to modify these terms at any time. Changes will
          be effective immediately upon posting. Your continued use of the
          Service constitutes acceptance of any changes.
        </p>

        <h2>10. Governing Law</h2>
        <p>
          These terms are governed by the laws of Australia. Any disputes will
          be subject to the exclusive jurisdiction of Australian courts.
        </p>

        <h2>11. Contact Information</h2>
        <p>
          If you have any questions about these Terms of Use, please contact us
          at{" "}
          <a href="mailto:mohamad.eldhaibi@gmail.com" className="static-link">
            mohamad.eldhaibi@gmail.com
          </a>
        </p>
      </section>
    </main>
  );
};

export default Terms;
