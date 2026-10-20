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
      {boxes.length > 0 ? (
        <ol className="item-list" aria-label={pageLabel}>
          {boxes.map((box, index) => (
            <li className="item-row" key={`${index}-${box.text}`}>
              <span className="item-main">{box.text}</span>
              {box.confidence !== null ? (
                <span className="label">{Math.round(box.confidence * 100)}%</span>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
