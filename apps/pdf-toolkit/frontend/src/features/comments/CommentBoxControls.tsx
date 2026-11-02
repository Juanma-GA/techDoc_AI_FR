import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Input } from "@internal/ui";
import { clampCommentBox, type CommentBox } from "./commentBox";

type BoxField = keyof CommentBox;

const fields: BoxField[] = ["x", "y", "width", "height"];

type CommentBoxControlsProps = {
  box: CommentBox;
  disabled: boolean;
  onChange: (box: CommentBox) => void;
};

export function CommentBoxControls({ box, disabled, onChange }: CommentBoxControlsProps) {
  const { t } = useTranslation();
  const id = useId();

  return (
    <div className="comments-box-controls" role="group" aria-label={t("comments.boxControls")}>
      {fields.map((field) => {
        const isSize = field === "width" || field === "height";
        const max = isSize ? (1 - box[field === "width" ? "x" : "y"]) * 100 : 99;
        return (
          <label className="comments-box-field" key={field} htmlFor={`${id}-${field}`}>
            <span>{t(`comments.box_${field}`)}</span>
            <Input
              id={`${id}-${field}`}
              type="number"
              min={isSize ? 1 : 0}
              max={Math.round(max * 10) / 10}
              step="0.1"
              value={Math.round(box[field] * 1000) / 10}
              disabled={disabled}
              onChange={(event) => {
                if (event.currentTarget.value === "") return;
                onChange(clampCommentBox({
                  ...box,
                  [field]: Number(event.currentTarget.value) / 100,
                }));
              }}
            />
          </label>
        );
      })}
    </div>
  );
}
