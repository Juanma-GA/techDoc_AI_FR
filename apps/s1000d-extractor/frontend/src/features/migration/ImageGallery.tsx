import { useTranslation } from "react-i18next";
import { wizardApi } from "../../lib/api";
import { splitImageNames } from "../../lib/imageClassification";

export function ImageGallery({ docId, names }: { docId: string; names: string[] }) {
  const { t } = useTranslation();
  const { illustrations, pictograms } = splitImageNames(names);
  return <>{[
    { names: illustrations, title: "images", alt: "imageAlt" },
    { names: pictograms, title: "pictograms", alt: "pictogramAlt" },
  ].map((group) => group.names.length ? <section key={group.title} className="space-y-3">
    <h3 className="font-semibold">{t(`migration.generate.${group.title}`, { count: group.names.length })}</h3>
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-8">
      {group.names.map((name, index) => <a key={name} href={wizardApi.imageUrl(docId, name)}
        target="_blank" rel="noreferrer" className="min-w-0 space-y-1">
        <img loading="lazy" decoding="async" src={wizardApi.thumbnailUrl(docId, name)}
          alt={t(`migration.generate.${group.alt}`, { index: index + 1 })}
          className="aspect-[4/3] w-full rounded-sm border border-md object-cover" />
        <span className="block truncate text-sm text-fg-dim" title={name}>{name}</span>
      </a>)}
    </div>
  </section> : null)}</>;
}
