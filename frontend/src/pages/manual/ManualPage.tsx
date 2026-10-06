import { Link } from 'react-router-dom';
import './Manual.css';

export interface ManualPageProps {
  /** The built manual in public/manual/ (static HTML, same origin → it follows the app's theme). */
  src: string;
  title: string;
  /** The other edition, offered as a one-click switch. */
  other: { to: string; label: string };
}

/**
 * Instrukcja obsługi — hosts the standalone manual pages in an iframe so the sidebar,
 * the bottom tab bar and the theme stay in place. Both editions are plain HTML with their own
 * table of contents and search (see public/manual/), so they also open on their own: the
 * "Otwórz w osobnej karcie" link is the print-friendly route (the manual hides its TOC when printed).
 */
export function ManualPage({ src, title, other }: ManualPageProps) {
  return (
    <div className="manual-page">
      <div className="manual-bar">
        <h1 className="manual-bar-title">{title}</h1>
        <Link to={other.to}>{other.label}</Link>
        <a href={src} target="_blank" rel="noopener noreferrer">
          Otwórz w osobnej karcie ↗
        </a>
      </div>
      <iframe className="manual-frame" src={src} title={title} />
    </div>
  );
}
