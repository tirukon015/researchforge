/**
 * The state a page is in most of the time before the database milestone.
 *
 * These are written to say what is true and what would change it, rather than
 * to apologise. A page that cannot show records yet should read as unbuilt,
 * not as broken - and never as empty because something failed.
 *
 * `art` opts into the compact ResearchForge mark. It is used sparingly: on the
 * one primary empty state per page, never on every card.
 */

import Image from "next/image";

export default function EmptyState({
  title,
  children,
  icon,
  art = false,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  art?: boolean;
  actions?: React.ReactNode;
}) {
  return (
    <div className="empty">
      {art ? (
        <Image
          src="/brand/researchforge-mark-192.png"
          alt=""
          width={56}
          height={44}
          className="empty__art"
        />
      ) : icon ? (
        <div className="empty__icon">{icon}</div>
      ) : null}
      <p className="empty__title">{title}</p>
      <div className="empty__body">{children}</div>
      {actions && <div className="empty__actions">{actions}</div>}
    </div>
  );
}
