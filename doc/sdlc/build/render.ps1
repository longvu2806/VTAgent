# Update the table of contents and fields in Word, save, and export a PDF for review.
param([string]$docx, [string]$pdf)
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $doc = $w.Documents.Open($docx)
  if ($doc.TablesOfContents.Count -gt 0) { $doc.TablesOfContents.Item(1).Update() }
  $doc.Fields.Update() | Out-Null
  $doc.Save()
  if ($pdf) { $doc.ExportAsFixedFormat($pdf, 17) }
  "pages: " + $doc.ComputeStatistics(2)
  $doc.Close()
} finally { $w.Quit() }
