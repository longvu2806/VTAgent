import { Link } from "@tanstack/react-router";
import logoDark from "@/assets/logo-dark.png";
import logoLight from "@/assets/logo-light.png";
import { MoonIcon, SunIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function TopBar() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-background px-4">
      <Link to="/" className="flex items-center gap-3 rounded-sm outline-offset-4">
        <img src={logoLight} alt="VTAgent" className="h-7 w-auto dark:hidden" />
        <img src={logoDark} alt="VTAgent" className="hidden h-7 w-auto dark:block" />
        <span className="hidden border-l pl-3 text-sm text-muted-foreground sm:inline">Trợ lý toàn diện</span>
      </Link>
      <div className="ml-auto flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger
            render={
              <span className="flex items-center gap-2 rounded-md px-2 py-1 text-sm text-muted-foreground">
                <span className="size-2 rounded-full bg-emerald-600 dark:bg-emerald-400" aria-hidden />
                Chạy trên máy này
              </span>
            }
          />
          <TooltipContent>Tài liệu, câu hỏi và mô hình đều ở trên máy; không gửi dữ liệu ra ngoài.</TooltipContent>
        </Tooltip>
        <Button
          variant="ghost"
          size="icon"
          aria-label={dark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
          onClick={() => setTheme(dark ? "light" : "dark")}
        >
          {dark ? <SunIcon /> : <MoonIcon />}
        </Button>
      </div>
    </header>
  );
}
