import { ArrowUpRight, Leaf, MessageCircle, ShieldCheck } from "lucide-react";
import { type ReactNode, useId } from "react";
import { Link } from "react-router-dom";
import "./AuthLayout.css";

type AuthLayoutProps = {
  children: ReactNode;
  eyebrow?: string;
  title?: string;
  description?: string;
};

/** Cadre partagé par l’authentification et le contact publics. */
export function AuthLayout({
  children,
  eyebrow = "VOTRE ESPACE GREENFINANCE",
  title,
  description,
}: AuthLayoutProps) {
  const headingId = useId();

  return (
    <div className="auth-page">
      <a className="auth-skip-link" href="#auth-content">
        Aller au formulaire
      </a>
      <div className="auth-container">
        <header className="auth-header">
          <Link to="/login" className="auth-brand" aria-label="GreenFinance-Scorer — connexion">
            <img src="/favicon.svg" alt="" width="44" height="44" />
            <span>
              <span className="auth-brand-name">
                GreenFinance<span>Scorer</span>
              </span>
              <span className="auth-brand-caption">LA FINANCE, DURABLEMENT.</span>
            </span>
          </Link>
        </header>

        <main id="auth-content" className="auth-main" tabIndex={-1}>
          <section className="auth-story" aria-label="La plateforme GreenFinance-Scorer">
            <div className="auth-kicker">
              <Leaf size={15} aria-hidden="true" /> INTELLIGENCE ESG & CARBONE
            </div>
            <h2 className="auth-story-title">
              La donnée éclaire.
              <br />
              <span>L’impact se mesure.</span>
            </h2>
            <div className="auth-illustration" aria-hidden="true">
              <div className="auth-illustration-inner">
                <div className="auth-illustration-grid" />
                <div className="auth-orbit auth-orbit-outer" />
                <div className="auth-orbit auth-orbit-inner" />
                <div className="auth-growth-line">
                  <svg viewBox="0 0 420 190" fill="none" aria-hidden="true">
                    <path
                      d="M10 162C73 162 73 115 135 115S206 140 254 81S329 91 397 24"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeDasharray="5 7"
                    />
                    <path
                      d="m380 24 18-1-1 18"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
                <div className="auth-pillar auth-pillar-social">
                  <span>S</span>
                  <span>Social</span>
                </div>
                <div className="auth-pillar auth-pillar-environment">
                  <Leaf size={32} strokeWidth={1.4} />
                  <span>E</span>
                  <span>Environnement</span>
                </div>
                <div className="auth-pillar auth-pillar-governance">
                  <span>G</span>
                  <span>Gouvernance</span>
                </div>
                <span className="auth-illustration-caption">
                  <ArrowUpRight size={16} /> Une vision commune. Un impact durable.
                </span>
              </div>
            </div>

            <div className="auth-story-footer">
              <ShieldCheck size={20} aria-hidden="true" />
              <p>
                Un espace pour chaque acteur.
                <br />
                <span>Des entreprises aux investisseurs, de la recherche à l’audit.</span>
              </p>
            </div>
          </section>

          <section className="auth-form-panel" aria-labelledby={headingId}>
            <div className="auth-panel-accent" />
            <div className="auth-form-heading">
              <img className="auth-form-logo" src="/favicon.svg" alt="" width="48" height="48" />
              <p className="auth-form-eyebrow" id={headingId}>
                {eyebrow}
              </p>
              {title ? <h1>{title}</h1> : null}
              {description ? <p className="auth-form-description">{description}</p> : null}
            </div>
            {children}
          </section>
        </main>

        <footer className="auth-footer">
          <span>© {new Date().getFullYear()} GreenFinance-Scorer</span>
          <Link to="/contact">
            <MessageCircle size={18} aria-hidden="true" /> Contactez-nous
          </Link>
        </footer>
      </div>
    </div>
  );
}
