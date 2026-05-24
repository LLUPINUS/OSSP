import { useVideoStore } from "../store/useVideoStore";

export default function CookingSteps() {
  const cookingSteps = useVideoStore((s) => s.cookingSteps);

  if (cookingSteps.length === 0) {
    return (
      <p className="text-sm text-gray-400 p-4">
        영상을 선택하면 요리 단계가 자동으로 추출됩니다.
      </p>
    );
  }

  return (
    <div className="w-full max-w-sm p-4">
      <h2 className="text-base font-semibold mb-3">요리 단계</h2>
      <ol className="space-y-2">
        {cookingSteps.map((step, i) => (
          <li
            key={i}
            className="p-3 rounded border text-sm border-gray-200"
          >
            <span className="text-gray-400 text-xs mr-2">
              {step.start_time} ~ {step.end_time}
            </span>
            {step.action}
          </li>
        ))}
      </ol>
    </div>
  );
}
