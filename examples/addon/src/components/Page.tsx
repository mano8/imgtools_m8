import type { ComponentChild } from "preact";

type PageType = {
  title: string;
  children: ComponentChild;
};

export default function Page({ title, children }: PageType) {
  return (
    <div className="w-full  border-2 rounded-xl">
      <h1 className="w-full mb-3 p-3 border-b-2">{title}</h1>
      <div className="mb-3 p-3">{children}</div>
    </div>
  );
}
