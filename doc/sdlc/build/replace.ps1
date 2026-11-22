# Replace a phrase everywhere in a .docx with Word's own Find/Replace (keeps formatting), then save.
param([string]$docx, [string]$find, [string]$replace)
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Open($docx)
  foreach ($story in $doc.StoryRanges) {
    # 2 = wdReplaceAll; 1 = wdFindContinue
    $story.Find.Execute($find, $false, $false, $false, $false, $false, $true, 1, $false, $replace, 2) | Out-Null
  }
  $doc.Save()
  $doc.Close()
} finally { $w.Quit() }
