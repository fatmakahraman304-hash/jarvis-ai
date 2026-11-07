param([long]$WindowHandle)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
if ($null -eq $root) { throw 'Active window not accessible' }
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$queue = New-Object System.Collections.Queue
$queue.Enqueue(@($root,0))
$nodes = New-Object System.Collections.Generic.List[object]
while ($queue.Count -gt 0 -and $nodes.Count -lt 220) {
 $entry = $queue.Dequeue(); $element = $entry[0]; $depth = [int]$entry[1]
 try {
  $c = $element.Current; $r = $c.BoundingRectangle
  if (-not $c.IsOffscreen -and -not $c.IsPassword -and $r.Width -gt 2 -and $r.Height -gt 2) {
   $nodes.Add(@{name=$c.Name; role=$c.ControlType.ProgrammaticName.Replace('ControlType.',''); automation_id=$c.AutomationId; enabled=$c.IsEnabled; rect=@($r.X,$r.Y,$r.Width,$r.Height)})
  }
  if ($depth -lt 10 -and -not $c.IsPassword) {
   $child=$walker.GetFirstChild($element); $siblings=0
   while ($null -ne $child -and $siblings -lt 100 -and $queue.Count -lt 500) {
    $queue.Enqueue(@($child,$depth+1)); $child=$walker.GetNextSibling($child); $siblings++
   }
  }
 } catch { }
}
@{window=$WindowHandle;title=$root.Current.Name;elements=$nodes.ToArray()} | ConvertTo-Json -Depth 5 -Compress
