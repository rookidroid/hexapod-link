// Building blocks of the panels over the view and of the dock, so they all lay
// their controls out the same way. Their markup and class names are the ones
// the Dash version of the app drew, so styles/industrial.css (and the widget
// base in styles/vendor/dash-widgets.css) style them as before.

import { type ReactNode, useEffect, useRef, useState } from "react";

export function FieldLabel({ children, id }: { children: ReactNode; id?: string }) {
    return (
        <label className="ind-field-label" id={id}>
            {children}
        </label>
    );
}

export function GroupHeader({ children }: { children: ReactNode }) {
    return <div className="ind-group-header">{children}</div>;
}

/** How a number is shown in a field: as typed, without float noise. */
function shown(value: number | null | undefined): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return "";
    return String(Number(value.toPrecision(12)));
}

function parsed(text: string): number | null {
    if (text.trim() === "") return null;
    const n = Number(text);
    return Number.isFinite(n) ? n : null;
}

/** A number input that applies what is typed when it is left or Enter is
 * pressed, not per digit; until then it shows what is being typed, and after
 * whatever it is given. */
export function NumberInput({
    value,
    onCommit,
    className = "form-control form-control-sm",
    id,
    step,
    placeholder,
    disabled,
    min,
}: {
    value: number | null | undefined;
    onCommit: (value: number | null) => void;
    className?: string;
    id?: string;
    step?: number | string;
    placeholder?: string;
    disabled?: boolean;
    min?: number;
}) {
    const [draft, setDraft] = useState<string | null>(null);
    const commit = () => {
        if (draft === null) return;
        const next = parsed(draft);
        setDraft(null);
        if (next !== value) onCommit(next);
    };
    return (
        <input
            type="number"
            className={className}
            id={id}
            step={step ?? "any"}
            min={min}
            placeholder={placeholder}
            disabled={disabled}
            value={draft ?? shown(value)}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
                if (e.key === "Enter") commit();
                if (e.key === "Escape") setDraft(null);
            }}
        />
    );
}

export function NumberField({
    id,
    label,
    value,
    onCommit,
    step = 1,
    min,
}: {
    id: string;
    label: string;
    value: number | null;
    onCommit: (value: number | null) => void;
    step?: number;
    min?: number;
}) {
    return (
        <div className="ind-number-field">
            <FieldLabel>{label}</FieldLabel>
            <NumberInput id={id} value={value} onCommit={onCommit} step={step} min={min} />
        </div>
    );
}

export function FieldGrid({ children, oneRow }: { children: ReactNode; oneRow?: boolean }) {
    return (
        <div className={oneRow ? "ind-field-grid ind-field-row" : "ind-field-grid"}>{children}</div>
    );
}

const decimals = (step: number) => {
    const text = String(step);
    return text.includes(".") ? text.split(".")[1].length : 0;
};

/** A slider: the track, and (with `input`) its value box at the right end, so
 * a value can be typed as well as dragged to. It shows `value`; dragging calls
 * onChange with each step, or only on letting go with `onRelease` alone. */
export function Slider({
    id,
    min,
    max,
    step,
    value,
    onChange,
    onGrab,
    onRelease,
    disabled,
    input = true,
}: {
    id?: string;
    min: number;
    max: number;
    step: number;
    value: number;
    onChange: (value: number) => void;
    onGrab?: () => void;
    onRelease?: (value: number) => void;
    disabled?: boolean;
    input?: boolean;
}) {
    const track = useRef<HTMLSpanElement>(null);
    const dragging = useRef(false);
    const last = useRef(value);
    const span = max - min || 1;
    const clamped = Math.min(Math.max(value, min), max);
    const fraction = (clamped - min) / span;

    const snap = (raw: number) => {
        const steps = Math.round((raw - min) / step);
        const v = min + steps * step;
        return Number(Math.min(Math.max(v, min), max).toFixed(decimals(step)));
    };
    const fromPointer = (clientX: number) => {
        const box = track.current!.getBoundingClientRect();
        return snap(min + ((clientX - box.left) / Math.max(box.width, 1)) * span);
    };
    const emit = (v: number) => {
        if (v !== last.current) {
            last.current = v;
            onChange(v);
        }
    };
    useEffect(() => {
        if (!dragging.current) last.current = value;
    }, [value]);

    const thumbOffset = 8 - 16 * fraction;
    return (
        <div id={id} className="dash-slider-container">
            {input && (
                <NumberInput
                    className="dash-input-container dash-range-slider-input  dash-range-slider-max-input"
                    value={value}
                    step={step}
                    disabled={disabled}
                    onCommit={(v) => {
                        if (v !== null) {
                            const next = snap(v);
                            onChange(next);
                            onRelease?.(next);
                        }
                    }}
                />
            )}
            <div className="dash-slider-wrapper">
                <span
                    ref={track}
                    dir="ltr"
                    data-orientation="horizontal"
                    aria-disabled={disabled ? "true" : "false"}
                    {...(disabled ? { "data-disabled": "" } : {})}
                    className="dash-slider-root"
                    data-included="true"
                    style={
                        {
                            "--radix-slider-thumb-transform": "translateX(-50%)",
                        } as React.CSSProperties
                    }
                    onPointerDown={(e) => {
                        if (disabled || e.button !== 0) return;
                        e.preventDefault();
                        e.currentTarget.setPointerCapture(e.pointerId);
                        dragging.current = true;
                        onGrab?.();
                        emit(fromPointer(e.clientX));
                        (
                            e.currentTarget.querySelector("[role=slider]") as HTMLElement | null
                        )?.focus();
                    }}
                    onPointerMove={(e) => {
                        if (dragging.current) emit(fromPointer(e.clientX));
                    }}
                    onPointerUp={() => {
                        if (!dragging.current) return;
                        dragging.current = false;
                        onRelease?.(last.current);
                    }}
                    onPointerCancel={() => {
                        if (!dragging.current) return;
                        dragging.current = false;
                        onRelease?.(last.current);
                    }}
                >
                    <span
                        data-orientation="horizontal"
                        className="dash-slider-track"
                        {...(disabled ? { "data-disabled": "" } : {})}
                    >
                        <span
                            data-orientation="horizontal"
                            className="dash-slider-range"
                            style={{ left: "0%", right: `${100 - fraction * 100}%` }}
                        />
                    </span>
                    <span
                        style={{
                            transform: "var(--radix-slider-thumb-transform)",
                            position: "absolute",
                            left: `calc(${fraction * 100}% + ${thumbOffset}px)`,
                        }}
                    >
                        <span
                            role="slider"
                            aria-valuemin={min}
                            aria-valuemax={max}
                            aria-valuenow={clamped}
                            aria-orientation="horizontal"
                            data-orientation="horizontal"
                            tabIndex={disabled ? undefined : 0}
                            className="dash-slider-thumb dash-slider-thumb-1"
                            {...(disabled ? { "data-disabled": "" } : {})}
                            onKeyDown={(e) => {
                                if (disabled) return;
                                const by: Record<string, number> = {
                                    ArrowRight: step,
                                    ArrowUp: step,
                                    ArrowLeft: -step,
                                    ArrowDown: -step,
                                    PageUp: step * 10,
                                    PageDown: -step * 10,
                                };
                                let next: number | null = null;
                                if (e.key in by) next = snap(clamped + by[e.key]);
                                if (e.key === "Home") next = min;
                                if (e.key === "End") next = max;
                                if (next === null) return;
                                e.preventDefault();
                                onGrab?.();
                                emit(next);
                            }}
                            onKeyUp={(e) => {
                                if (!disabled && e.key.startsWith("Arrow"))
                                    onRelease?.(last.current);
                            }}
                        />
                    </span>
                </span>
            </div>
        </div>
    );
}

/** A slider on one line: its label, the track, and its value box. */
export function SliderField({
    id,
    label,
    min,
    max,
    step,
    value,
    onChange,
    disabled,
    className = "",
    title,
}: {
    id?: string;
    label: string;
    min: number;
    max: number;
    step: number;
    value: number;
    onChange: (value: number) => void;
    disabled?: boolean;
    className?: string;
    title?: string;
}) {
    return (
        <div
            className={`ind-inline-slider ${className}`.trim()}
            title={title ?? `${min} to ${max}`}
        >
            <FieldLabel>{label}</FieldLabel>
            <Slider
                id={id}
                min={min}
                max={max}
                step={step}
                value={value}
                onChange={onChange}
                disabled={disabled}
            />
        </div>
    );
}

/** A segmented choice, as dbc.RadioItems drew it. */
export function Segmented<T extends string>({
    id,
    options,
    value,
    onChange,
    className = "dock-seg",
}: {
    id: string;
    options: { label: ReactNode; value: T }[];
    value: T;
    onChange: (value: T) => void;
    className?: string;
}) {
    return (
        <div id={id} className={className}>
            {options.map((option) => {
                const inputId = `${id}-${option.value}`;
                const active = option.value === value;
                return (
                    <div className="form-check" key={option.value}>
                        <input
                            id={inputId}
                            className="form-check-input btn-check"
                            type="radio"
                            value={option.value}
                            checked={active}
                            onChange={() => onChange(option.value)}
                        />
                        <label
                            className={`form-check-label dock-seg-item${active ? " active" : ""}`}
                            htmlFor={inputId}
                        >
                            {option.label}
                        </label>
                    </div>
                );
            })}
        </div>
    );
}

/** One checkbox, as dcc.Checklist drew it. */
export function Check({
    id,
    label,
    checked,
    onChange,
    className = "",
}: {
    id: string;
    label: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    className?: string;
}) {
    return (
        <div id={id} className={`dash-options-list dash-checklist ${className}`.trim()}>
            <label className="dash-options-list-option">
                <span className="dash-options-list-option-wrapper">
                    <input
                        type="checkbox"
                        className="dash-options-list-option-checkbox"
                        checked={checked}
                        onChange={(e) => onChange(e.target.checked)}
                    />
                </span>
                <span className="dash-options-list-option-text">
                    <span>{label}</span>
                </span>
            </label>
        </div>
    );
}

export function Button({
    children,
    color = "secondary",
    outline = false,
    className = "",
    ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    color?: "primary" | "secondary" | "success" | "danger";
    outline?: boolean;
}) {
    return (
        <button
            type="button"
            className={`${className} btn btn-${outline ? "outline-" : ""}${color} btn-sm`.trim()}
            {...props}
        >
            {children}
        </button>
    );
}

/** A panel over the view that folds away, a native <details>. Only a click on
 * its title folds or opens it by hand; `open` is what the page says. */
export function Hud({
    id,
    className,
    open,
    onToggle,
    summary,
    summaryTitle,
    children,
}: {
    id: string;
    className: string;
    open: boolean;
    onToggle: (open: boolean) => void;
    summary: ReactNode;
    summaryTitle?: string;
    children: ReactNode;
}) {
    return (
        <details id={id} className={className} open={open}>
            <summary
                title={summaryTitle}
                onClick={(e) => {
                    e.preventDefault();
                    onToggle(!open);
                }}
            >
                {summary}
            </summary>
            {children}
        </details>
    );
}
