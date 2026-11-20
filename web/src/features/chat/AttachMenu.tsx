// The composer's "+" menu: upload documents, or choose which documents the next
// question is limited to (FR-01, FR-14).
import { FilesIcon, PlusIcon, UploadIcon } from "lucide-react";
import { useRef } from "react";
import { useDocuments } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ACCEPTED, uploadFiles } from "@/features/documents/uploads";
import { GENRE } from "@/lib/labels";
import { useUi } from "@/stores/ui";

export function AttachMenu() {
  const input = useRef<HTMLInputElement>(null);
  const { data: documents = [] } = useDocuments();
  const { scope, toggleScope, clearScope } = useUi();

  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPTED}
        hidden
        onChange={(e) => {
          uploadFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button type="button" variant="ghost" size="icon" className="rounded-full" aria-label="Thêm tài liệu" />}
        >
          <PlusIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" className="w-60">
          <DropdownMenuItem onClick={() => input.current?.click()}>
            <UploadIcon />
            <span className="flex flex-col">
              Tải tài liệu lên
              <span className="text-xs text-muted-foreground">PDF hoặc DOCX</span>
            </span>
          </DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <FilesIcon />
              Chọn tài liệu để hỏi
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-80">
              <DropdownMenuCheckboxItem checked={scope.length === 0} onCheckedChange={clearScope}>
                Tất cả {documents.length} tài liệu
              </DropdownMenuCheckboxItem>
              <DropdownMenuSeparator />
              {documents.map((d) => (
                <DropdownMenuCheckboxItem
                  key={d.id}
                  checked={scope.includes(d.id)}
                  onCheckedChange={() => toggleScope(d.id)}
                  closeOnClick={false}
                >
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{d.title ?? d.current_version.file_name}</span>
                    <span className="text-xs text-muted-foreground">{GENRE[d.genre]}</span>
                  </span>
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
}
