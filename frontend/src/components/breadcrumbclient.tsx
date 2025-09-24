"use client";

import { usePathname } from "next/navigation";
import { BreadcrumbPage } from "./ui/breadcrumb";

export default function BreadcrumbClient() {
  const pathname = usePathname();
  return (
    <BreadcrumbPage>
      {pathname === "/" && "Home"}
      {pathname === "/create" && "Create"}
    </BreadcrumbPage>
  );
}
