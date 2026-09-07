import type { ReactNode } from "react";

/** Шапка = фирменный баннер Велесстрой Монтаж + опциональная строка-подзаголовок */
export function BrandHeader({
  title,
  subtitle,
  right,
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="brand-strip" aria-label="Велесстрой Монтаж · ОП Кингисепп">
      <div className="brand-strip-banner">
        <img
          className="brand-strip-img"
          src="./brand/header-banner.png"
          alt="Велесстрой Монтаж — ОП Кингисепп · система оценки персонала"
        />
        {right && <div className="brand-strip-actions">{right}</div>}
      </div>
      {(title || subtitle) && (
        <div className="brand-strip-info">
          {title && <strong className="brand-strip-title">{title}</strong>}
          {subtitle && <span className="brand-strip-sub">{subtitle}</span>}
        </div>
      )}
    </header>
  );
}
