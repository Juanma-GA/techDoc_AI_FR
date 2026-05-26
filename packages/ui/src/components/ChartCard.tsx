import { type ReactNode } from "react";

import { cn } from "../lib/utils";
import { Badge, type BadgeProps } from "./Badge";
import { Card, CardContent, CardHeader, CardTitle } from "./Card";

export type ChartCardProps = {
  title: string;
  badge?: { label: string; variant?: BadgeProps["variant"] };
  wide?: boolean;
  children: ReactNode;
  className?: string;
};

export function ChartCard({ title, badge, wide, children, className }: ChartCardProps) {
  return (
    <Card className={cn(wide ? "col-span-full" : null, className)}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 p-4">
        <CardTitle className="text-base">{title}</CardTitle>
        {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
