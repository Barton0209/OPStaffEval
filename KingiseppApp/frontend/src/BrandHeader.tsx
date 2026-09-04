import type { ReactNode } from "react";

/** Шапка: логотип ВелесстройМонтаж фоном, растянут вправо */
export function BrandHeader({
  title = "Отдел мобилизации и координации ОП Кингисепп",
  subtitle,
  right,
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="corp-header corp-header-banner">
      <div className="corp-banner-bg" aria-hidden>
        <img src="./logo-velesstroy.png" alt="" />
      </div>
      <div className="corp-header-inner">
        <div className="corp-titles">
          <p className="brand">ВелесстройМонтаж · Кингисепп</p>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        {right && <div className="corp-actions">{right}</div>}
      </div>
    </header>
  );
}
