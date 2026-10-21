import type { OcrBox } from "../../types/preparation";

export function OcrPagePreview({
  imageUrl,
  boxes,
  pageLabel,
}: {
  imageUrl: string;
  boxes: OcrBox[];
  pageLabel: string;
}) {
  return (
    <div>
      <div className="preparation-ocr-preview" role="img" aria-label={pageLabel}>
        <img src={imageUrl} alt="" />
        {boxes.map((box, index) => (
          <span
            key={`${index}-${box.x0}-${box.y0}`}
            className="preparation-ocr-box"
            aria-hidden="true"
            title={box.text}
            style={{
              left: `${box.x0 * 100}%`,
              top: `${box.y0 * 100}%`,
              width: `${(box.x1 - box.x0) * 100}%`,
              height: `${(box.y1 - box.y0) * 100}%`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
