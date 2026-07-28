# frontend

[ai-ops-agent](../README.md) の chat UI(Next.js App Router + TypeScript + Tailwind CSS +
shadcn/ui)。全体構成・アーキテクチャは[ルートのREADME](../README.md)と
[CLAUDE.md](../CLAUDE.md)を参照してください。

## ローカルでの起動

```bash
npm install
CHAT_API_URL=http://localhost:8003 npm run dev
```

`http://localhost:3000` で起動します(`chat_api`が別途 `http://localhost:8003` で
起動している必要があります)。

Docker Compose経由での起動方法はルートのREADMEを参照してください。
