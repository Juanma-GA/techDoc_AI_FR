// Atoms
export {
  AppShell,
  SidebarNavContent,
  sidebarNavItemClass,
  type AppShellProps,
  type SidebarNavIconName,
  type SidebarNavContentProps,
} from "./components/AppShell";
export {
  Ai4TechDocLogo,
  setAi4TechDocFavicon,
  type Ai4TechDocLogoProps,
} from "./components/Ai4TechDocLogo";
export { Badge, badgeVariants, type BadgeProps } from "./components/Badge";
export { Button, buttonVariants, type ButtonProps } from "./components/Button";
export { Card, CardContent, CardHeader, CardTitle } from "./components/Card";
export { Checkbox, type CheckboxProps } from "./components/Checkbox";
export { Input, inputVariants, type InputProps } from "./components/Input";
export {
  Select,
  selectVariants,
  type SelectOption,
  type SelectProps,
} from "./components/Select";
export { Spinner, type SpinnerProps } from "./components/Spinner";
export { Switch, type SwitchProps } from "./components/Switch";
export {
  Textarea,
  textareaVariants,
  type TextareaProps,
} from "./components/Textarea";
export { Skeleton } from "./components/Skeleton";

// Layout & forms
export { PageHeader, type PageHeaderProps } from "./components/PageHeader";
export { FormField, type FormFieldProps } from "./components/FormField";
export {
  CollapsibleSection,
  type CollapsibleSectionProps,
} from "./components/CollapsibleSection";
export { Alert, alertVariants, type AlertProps } from "./components/Alert";
export { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/Tabs";
export {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./components/Table";
export {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
  type TooltipProps,
} from "./components/Tooltip";

// Business
export { ChartCard, type ChartCardProps } from "./components/ChartCard";
export {
  DemoModeBadge,
  DemoModeProvider,
  DemoModeSelector,
  useDemoMode,
  type DemoMode,
  type DemoModeBadgeProps,
  type DemoModeContextValue,
  type DemoModeProviderProps,
  type DemoModeSelectorProps,
} from "./components/DemoMode";
export {
  DemoScenarioPanel,
  type DemoScenarioPanelLabels,
  type DemoScenarioPanelProps,
} from "./components/DemoScenarioPanel";
export { EmptyState, type EmptyStateProps } from "./components/EmptyState";
export { FileDropzone, type FileDropzoneProps } from "./components/FileDropzone";
export { KpiCard, type KpiCardProps, type KpiDelta } from "./components/KpiCard";
export { LanguageSwitcher, type LanguageSwitcherProps } from "./components/LanguageSwitcher";
export { LoadingOverlay, type LoadingOverlayProps } from "./components/LoadingOverlay";
export { LlmStatus, type LlmStatusLabels, type LlmStatusProps } from "./components/LlmStatus";
export { MarkdownView, type MarkdownViewProps } from "./components/MarkdownView";
export { PortalLink, portalHref, type PortalLinkProps } from "./components/PortalLink";
export {
  MultiSelect,
  type MultiSelectItem,
  type MultiSelectProps,
} from "./components/MultiSelect";
export { Slicer, type SlicerItem, type SlicerProps } from "./components/Slicer";

// Overlays (replace alert / confirm)
export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
} from "./components/Dialog";
export {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  Toaster,
  type ToastProps,
  type ToastVariant,
} from "./components/Toast";

// Theme
export { ThemeToggle, type ThemeToggleProps } from "./components/ThemeToggle";

// Error handling
export { ErrorBoundary, type ErrorBoundaryProps } from "./components/ErrorBoundary";

// Hooks & utils
export { useMediaQuery } from "./hooks/useMediaQuery";
export { cn } from "./lib/utils";
export {
  createDemoFile,
  type DemoInputField,
  type DemoSampleFile,
  type DemoScenario,
  type DemoScenarioContext,
  type DemoScenarioResult,
} from "./lib/demo";
