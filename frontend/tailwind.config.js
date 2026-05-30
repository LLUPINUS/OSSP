/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // CookSync 디자인 토큰 (CookSync_handoff/README.md 3. 디자인 시스템)
      colors: {
        ink: {
          DEFAULT: "#171717", // 기본 텍스트, 주요 버튼 배경
          2: "#525252", // 보조 텍스트
          3: "#8a8a8a", // placeholder, 메타, 비활성
        },
        line: "#ededed", // 구분선
        fill: "#f6f6f5", // 입력창/카드 배경
        accent: {
          DEFAULT: "#ff5a2c", // 브랜드 코랄, 강조
          ink: "#e8430f", // 강조 텍스트(가독성 보정)
        },
        success: "#1f8a5b", // 인식 성공(초록)
      },
      fontFamily: {
        sans: [
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
}
