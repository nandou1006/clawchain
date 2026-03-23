"use client";

import { useEffect, useRef, useCallback } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, dropCursor, rectangularSelection, crosshairCursor, highlightSpecialChars, keymap, ViewUpdate } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { syntaxHighlighting, indentOnInput, bracketMatching, foldGutter, defaultHighlightStyle, HighlightStyle } from "@codemirror/language";
import { oneDark } from "@codemirror/theme-one-dark";
import { tags } from "@lezer/highlight";

// Custom light theme
const lightTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--bg-elevated, #fff)",
    color: "var(--text, #333)",
    height: "100%",
  },
  ".cm-content": {
    caretColor: "var(--accent, #007acc)",
    fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
    fontSize: "12px",
    lineHeight: "1.5",
    padding: "8px 0",
  },
  ".cm-cursor": {
    borderLeftColor: "var(--accent, #007acc)",
  },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
    backgroundColor: "var(--accent-muted, #b3d7ff) !important",
  },
  ".cm-activeLine": {
    backgroundColor: "var(--hover, #f5f5f5)",
  },
  ".cm-gutters": {
    backgroundColor: "var(--bg-inset, #fafafa)",
    color: "var(--text-tertiary, #999)",
    border: "none",
    borderRight: "1px solid var(--border, #e5e5e5)",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "var(--hover, #f0f0f0)",
  },
  ".cm-foldGutter": {
    width: "12px",
  },
  ".cm-scroller": {
    overflow: "auto",
  },
}, { dark: false });

// Custom dark highlight style
const darkHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: "#c678dd" },
  { tag: tags.string, color: "#98c379" },
  { tag: tags.number, color: "#d19a66" },
  { tag: tags.bool, color: "#56b6c2" },
  { tag: tags.null, color: "#56b6c2" },
  { tag: tags.comment, color: "#5c6370", fontStyle: "italic" },
  { tag: tags.heading, color: "#e06c75", fontWeight: "bold" },
  { tag: tags.strong, color: "#e5c07b", fontWeight: "bold" },
  { tag: tags.emphasis, color: "#c678dd", fontStyle: "italic" },
  { tag: tags.url, color: "#61afef" },
]);

interface CodeMirrorEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: "json" | "markdown";
  theme?: "light" | "dark";
  height?: string;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
}

export default function CodeMirrorEditor({
  value,
  onChange,
  language = "markdown",
  theme = "light",
  height = "100%",
  readOnly = false,
  placeholder = "",
  className = "",
}: CodeMirrorEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);

  // Keep onChange ref updated
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // Handle value changes from outside
  const isExternalUpdate = useRef(false);

  const updateListener = useCallback((update: ViewUpdate) => {
    if (update.docChanged && !isExternalUpdate.current) {
      const newValue = update.state.doc.toString();
      onChangeRef.current?.(newValue);
    }
  }, []);

  // Initialize editor
  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      highlightSpecialChars(),
      history(),
      foldGutter(),
      drawSelection(),
      dropCursor(),
      EditorState.allowMultipleSelections.of(true),
      indentOnInput(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      rectangularSelection(),
      crosshairCursor(),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.updateListener.of(updateListener),
      EditorView.lineWrapping,
      EditorState.tabSize.of(2),
    ];

    // Add language support
    if (language === "json") {
      extensions.push(json());
      extensions.push(bracketMatching({ brackets: "()[]{}" }));
    } else {
      extensions.push(markdown());
    }

    // Add theme
    if (theme === "dark") {
      extensions.push(oneDark);
      extensions.push(syntaxHighlighting(darkHighlightStyle, { fallback: true }));
    } else {
      extensions.push(lightTheme);
    }

    // Add readonly
    if (readOnly) {
      extensions.push(EditorState.readOnly.of(true));
    }

    const state = EditorState.create({
      doc: value,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [language, theme, readOnly, updateListener]);

  // Sync external value changes
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;

    const currentValue = view.state.doc.toString();
    if (value !== currentValue) {
      isExternalUpdate.current = true;
      view.dispatch({
        changes: { from: 0, to: currentValue.length, insert: value },
      });
      isExternalUpdate.current = false;
    }
  }, [value]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height, overflow: "hidden" }}
    />
  );
}