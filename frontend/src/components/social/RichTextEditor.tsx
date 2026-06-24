"use client";

import { useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Underline from "@tiptap/extension-underline";
import EmojiPicker, { Theme } from "emoji-picker-react";
import {
  Bold, Italic, Underline as UnderlineIcon, Heading1, Heading2, Quote,
  List, ListOrdered, Link as LinkIcon, Image as ImageIcon, Smile, Film, Undo, Redo,
} from "lucide-react";
import GifPicker from "./GifPicker";

function Btn({ active, onClick, title, children }: { active?: boolean; onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`rounded-lg p-1.5 transition-colors ${
        active ? "bg-brand-100 text-brand-700 dark:bg-slate-700 dark:text-brand-300" : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

export default function RichTextEditor({
  content,
  onChange,
  placeholder = "開始輸入…",
}: {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
}) {
  const [showEmoji, setShowEmoji] = useState(false);
  const [showGif, setShowGif] = useState(false);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder }),
      Image.configure({ inline: false, HTMLAttributes: { class: "rounded-lg" } }),
      Link.configure({ openOnClick: false, HTMLAttributes: { rel: "noreferrer", target: "_blank" } }),
      Underline,
    ],
    content,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
    editorProps: {
      attributes: {
        class: "markdown min-h-[180px] rounded-xl border border-slate-300 bg-white p-3 outline-none focus:border-brand-500 dark:border-slate-600 dark:bg-slate-900",
      },
    },
  });

  if (!editor) return null;

  const addLink = () => {
    const url = window.prompt("輸入連結網址");
    if (url) editor.chain().focus().setLink({ href: url }).run();
  };
  const addImage = () => {
    const url = window.prompt("輸入圖片網址");
    if (url) editor.chain().focus().setImage({ src: url }).run();
  };

  return (
    <div className="space-y-1.5">
      <div className="relative flex flex-wrap items-center gap-0.5 rounded-xl border border-slate-200 bg-slate-50 p-1.5 dark:border-slate-700 dark:bg-slate-800">
        <Btn active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} title="粗體"><Bold className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} title="斜體"><Italic className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()} title="底線"><UnderlineIcon className="h-4 w-4" /></Btn>
        <span className="mx-0.5 h-5 w-px bg-slate-200 dark:bg-slate-600" />
        <Btn active={editor.isActive("heading", { level: 1 })} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} title="標題1"><Heading1 className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} title="標題2"><Heading2 className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()} title="引言"><Quote className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()} title="清單"><List className="h-4 w-4" /></Btn>
        <Btn active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="編號清單"><ListOrdered className="h-4 w-4" /></Btn>
        <span className="mx-0.5 h-5 w-px bg-slate-200 dark:bg-slate-600" />
        <Btn active={editor.isActive("link")} onClick={addLink} title="連結"><LinkIcon className="h-4 w-4" /></Btn>
        <Btn onClick={addImage} title="圖片"><ImageIcon className="h-4 w-4" /></Btn>

        <div className="relative">
          <Btn active={showEmoji} onClick={() => { setShowEmoji((s) => !s); setShowGif(false); }} title="表情"><Smile className="h-4 w-4" /></Btn>
          {showEmoji && (
            <div className="absolute bottom-12 left-0 z-30">
              <EmojiPicker
                theme={Theme.AUTO}
                onEmojiClick={(e) => { editor.chain().focus().insertContent(e.emoji).run(); setShowEmoji(false); }}
                width={300}
                height={360}
              />
            </div>
          )}
        </div>

        <div className="relative">
          <Btn active={showGif} onClick={() => { setShowGif((s) => !s); setShowEmoji(false); }} title="GIF / 貼圖"><Film className="h-4 w-4" /></Btn>
          {showGif && (
            <GifPicker
              onSelect={(url) => { editor.chain().focus().setImage({ src: url }).run(); setShowGif(false); }}
              onClose={() => setShowGif(false)}
            />
          )}
        </div>

        <span className="mx-0.5 h-5 w-px bg-slate-200 dark:bg-slate-600" />
        <Btn onClick={() => editor.chain().focus().undo().run()} title="復原"><Undo className="h-4 w-4" /></Btn>
        <Btn onClick={() => editor.chain().focus().redo().run()} title="重做"><Redo className="h-4 w-4" /></Btn>
      </div>

      <EditorContent editor={editor} />
    </div>
  );
}
