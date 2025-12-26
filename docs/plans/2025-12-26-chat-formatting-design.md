# Chat Response Formatting Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render markdown in assistant chat responses for better readability.

**Architecture:** Add react-markdown to ChatMessage component with minimal styling changes.

**Tech Stack:** react-markdown, @tailwindcss/typography (optional)

---

## Scope

**In scope:**
- Markdown rendering for assistant messages (headers, lists, bold, italic, links)
- Basic code block styling (monospace, dark background, no syntax highlighting)
- Keep current compact style with minor spacing adjustments

**Out of scope:**
- Syntax highlighting for code blocks
- Inline citations (sources remain as badges at bottom)
- User message formatting (stay as plain text)
- Backend changes

---

## Implementation

### Task 1: Add Dependencies

**Files:**
- Modify: `frontend/package.json`

**Steps:**

1. Install react-markdown:
   ```bash
   cd frontend && npm install react-markdown
   ```

2. Install tailwind typography plugin:
   ```bash
   npm install @tailwindcss/typography
   ```

3. Update `tailwind.config.js` to add the plugin:
   ```js
   plugins: [require('@tailwindcss/typography')],
   ```

4. Commit:
   ```bash
   git add package.json package-lock.json tailwind.config.js
   git commit -m "chore: add react-markdown and typography plugin"
   ```

---

### Task 2: Update ChatMessage Component

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.tsx`

**Steps:**

1. Add import:
   ```tsx
   import ReactMarkdown from 'react-markdown';
   ```

2. Replace content rendering for assistant messages:
   ```tsx
   {role === 'assistant' ? (
     <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-headings:my-3 prose-headings:font-semibold">
       <ReactMarkdown
         components={{
           code: ({ inline, children, ...props }) =>
             inline ? (
               <code className="bg-muted px-1 py-0.5 rounded text-sm" {...props}>
                 {children}
               </code>
             ) : (
               <pre className="bg-muted p-3 rounded-md overflow-x-auto">
                 <code {...props}>{children}</code>
               </pre>
             ),
         }}
       >
         {content}
       </ReactMarkdown>
     </div>
   ) : (
     <p className="whitespace-pre-wrap">{content}</p>
   )}
   ```

3. Run tests to verify nothing breaks:
   ```bash
   npm test
   ```

4. Commit:
   ```bash
   git add frontend/src/components/chat/ChatMessage.tsx
   git commit -m "feat: add markdown rendering to chat messages"
   ```

---

### Task 3: Manual Testing

**Steps:**

1. Start frontend dev server:
   ```bash
   cd frontend && npm run dev
   ```

2. Test with various markdown content:
   - Headers: `# H1`, `## H2`, `### H3`
   - Lists: `- item`, `1. item`
   - Bold/italic: `**bold**`, `*italic*`
   - Code: `` `inline` ``, ``` ```block``` ```
   - Links: `[text](url)`

3. Verify:
   - Compact spacing maintained
   - Dark mode works (`dark:prose-invert`)
   - Code blocks have dark background
   - Streaming still works (partial markdown renders gracefully)

---

## Files Summary

| File | Change |
|------|--------|
| `frontend/package.json` | Add react-markdown, @tailwindcss/typography |
| `frontend/tailwind.config.js` | Add typography plugin |
| `frontend/src/components/chat/ChatMessage.tsx` | Add ReactMarkdown rendering |

---

## Estimated Effort

Small - 3 tasks, ~30 minutes total.
