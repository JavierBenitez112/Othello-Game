FROM node:22-alpine

WORKDIR /app

COPY package.json package.json
COPY tsconfig.json tsconfig.json
COPY postcss.config.js postcss.config.js
COPY tailwind.config.ts tailwind.config.ts
COPY next.config.ts next.config.ts
COPY next-env.d.ts next-env.d.ts
COPY app app
COPY components components
COPY lib lib
COPY public public

RUN npm install
RUN npm run build

ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000

EXPOSE 3000

CMD ["npm", "run", "start"]
