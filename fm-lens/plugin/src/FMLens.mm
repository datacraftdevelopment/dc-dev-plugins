//
//  FMLens.mm — FM Lens plug-in for Claris FileMaker Pro
//
//  Purpose-built for agentic development: gives a coding agent eyes and hands
//  inside FileMaker Pro's own process — window/web-viewer snapshots (no macOS
//  Screen Recording permission), state probes, script starting, FileMaker XML
//  clipboard access, and a drop-folder command channel driven from the
//  plug-in idle loop.
//
//  Functions registered (plugin ID 'ADTh', kept from ADT Helper so calcs
//  written against the old names keep resolving; FileMaker stores the ID and
//  shows the new names):
//    FMLens_Version                                    -> version string
//    FMLens_WindowList                                 -> JSON array of open windows
//    FMLens_WindowSnapshot( path { ; windowTitle } )   -> writes PNG, "OK …" | "ERROR: …"
//    FMLens_Snapshot( path ; optionsJSON )             -> snapshot with region/scale options
//    FMLens_WebViewerSnapshot( path { ; windowTitle ; index } ) -> WKWebView pixels
//    FMLens_WebViewerList( { windowTitle } )           -> JSON of a window's web viewers
//    FMLens_State                                      -> JSON of Get() probes
//    FMLens_RunScript( fileName ; scriptName { ; param ; control } ) -> queue a script
//    FMLens_ClipboardFormats                           -> JSON of pasteboard flavors
//    FMLens_ClipboardGetXML( { code } )                -> FileMaker XML off the clipboard
//    FMLens_ClipboardSetXML( xml { ; code } )          -> FileMaker XML onto the clipboard
//    FMLens_ChannelStart( folder )                     -> begin idle-loop command channel
//    FMLens_ChannelStop                                -> end it
//    FMLens_ChannelStatus                              -> JSON status
//
//  Channels (JSON command files; `help` lists the verbs):
//    ~/.fm-lens/<app>/<file>   file channel, FileMaker idle loop, every verb
//    ~/.fm-lens/<app>/_app     app channel, Cocoa timer, UI verbs only; keeps
//                              working while a modal dialog is up
//  Both need ~/.fm-lens/config.json consent (legacy ~/.adt-helper/config.json
//  is read when the new file is absent).
//
//  Built against the Claris FileMaker Plug-In SDK (FMWrapper). The SDK's
//  license permits compiling plug-ins for use with Claris products.
//

#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <CoreServices/CoreServices.h>

#include "FMWrapper/FMXTypes.h"
#include "FMWrapper/FMXText.h"
#include "FMWrapper/FMXFixPt.h"
#include "FMWrapper/FMXData.h"
#include "FMWrapper/FMXCalcEngine.h"
#include "FMWrapper/FMXExtern.h"

#include <string>
#include <vector>

static const char* kADTh( "ADTh" );
static const char* kVersionString( "FM Lens 0.5.0" );

enum {
    kFML_VersionID            = 100,
    kFML_WindowListID         = 200,
    kFML_WindowSnapshotID     = 300,
    kFML_SnapshotID           = 310,
    kFML_WebViewerSnapshotID  = 320,
    kFML_WebViewerListID      = 330,
    kFML_StateID              = 400,
    kFML_RunScriptID          = 500,
    kFML_ClipboardFormatsID   = 600,
    kFML_ClipboardGetXMLID    = 610,
    kFML_ClipboardSetXMLID    = 620,
    kFML_ChannelStartID       = 700,
    kFML_ChannelStopID        = 710,
    kFML_ChannelStatusID      = 720,
};

// ---- fmx <-> Foundation helpers ---------------------------------------------------------

static NSString* NSStringFromFMXText( const fmx::Text& txt )
{
    const fmx::uint32 size = txt.GetSize();
    if (size == 0) return @"";
    std::vector<fmx::unichar16> buf( size );
    txt.GetUnicode( buf.data(), 0, size );
    return [NSString stringWithCharacters:reinterpret_cast<const unichar*>(buf.data()) length:size];
}

static void AssignFMXText( fmx::Text& txt, NSString* str )
{
    txt.Assign( str.UTF8String ? str.UTF8String : "", fmx::Text::kEncoding_UTF8 );
}

static void SetTextResult( fmx::Data& results, NSString* str )
{
    fmx::TextUniquePtr out;
    AssignFMXText( *out, str );
    results.SetAsText( *out, results.GetLocale() );
}

static void RunOnMain( void (^block)(void) )
{
    if ([NSThread isMainThread]) { block(); }
    else { dispatch_sync( dispatch_get_main_queue(), block ); }
}

static NSString* JSONString( id obj )
{
    if (obj == nil) return @"null";
    NSData* d = [NSJSONSerialization dataWithJSONObject:obj options:NSJSONWritingPrettyPrinted error:nil];
    if (!d) return @"null";
    return [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
}

// Evaluate a FileMaker calc expression through an environment; nil on error.
static NSString* EvalExpr( const fmx::ExprEnv& env, NSString* expr )
{
    fmx::TextUniquePtr t;
    AssignFMXText( *t, [NSString stringWithFormat:@"GetAsText ( %@ )", expr] );
    fmx::DataUniquePtr d;
    if (env.Evaluate( *t, *d ) != 0) return nil;
    return NSStringFromFMXText( d->GetAsText() );
}

// ---- window + snapshot core -------------------------------------------------------------

static NSWindow* FindWindow( NSString* title )
{
    for (NSWindow* w in [NSApp orderedWindows])
    {
        if (!w.isVisible || w.isMiniaturized) continue;
        if (title.length > 0)
        {
            if ([w.title localizedCaseInsensitiveContainsString:title]) return w;
        }
        else if (w.title.length > 0) return w;
    }
    return nil;
}

// Capture a window's content view. region (in view points, top-left origin) may be
// NSZeroRect for the whole view; scale 0 keeps the backing scale, 1 forces 1x output.
static NSString* SnapshotWindowCore( NSWindow* target, NSRect region, CGFloat scale, NSString* path )
{
    NSView* view = target.contentView;
    NSRect bounds = view.bounds;
    if (bounds.size.width < 1 || bounds.size.height < 1)
        return @"ERROR: window content view has zero size";

    NSRect capture = bounds;
    if (!NSIsEmptyRect( region ))
    {
        // convert from top-left-origin points to the view's coordinate space
        NSRect r = region;
        if (!view.isFlipped)
            r.origin.y = bounds.size.height - region.origin.y - region.size.height;
        capture = NSIntersectionRect( r, bounds );
        if (NSIsEmptyRect( capture ))
            return @"ERROR: region lies outside the window content";
    }

    NSBitmapImageRep* rep = [view bitmapImageRepForCachingDisplayInRect:capture];
    if (rep == nil) return @"ERROR: could not allocate bitmap";
    [view cacheDisplayInRect:capture toBitmapImageRep:rep];

    // optional resample to an exact scale (points * scale)
    if (scale > 0.01)
    {
        const NSInteger outW = (NSInteger)llround( capture.size.width  * scale );
        const NSInteger outH = (NSInteger)llround( capture.size.height * scale );
        if (outW != rep.pixelsWide || outH != rep.pixelsHigh)
        {
            NSBitmapImageRep* scaled = [[NSBitmapImageRep alloc]
                initWithBitmapDataPlanes:NULL pixelsWide:outW pixelsHigh:outH
                bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO
                colorSpaceName:NSCalibratedRGBColorSpace bytesPerRow:0 bitsPerPixel:0];
            if (scaled)
            {
                NSGraphicsContext* ctx = [NSGraphicsContext graphicsContextWithBitmapImageRep:scaled];
                [NSGraphicsContext saveGraphicsState];
                [NSGraphicsContext setCurrentContext:ctx];
                ctx.imageInterpolation = NSImageInterpolationHigh;
                [rep drawInRect:NSMakeRect( 0, 0, outW, outH )];
                [NSGraphicsContext restoreGraphicsState];
                rep = scaled;
            }
        }
    }

    NSData* png = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
    if (png == nil) return @"ERROR: PNG encoding failed";

    [[NSFileManager defaultManager] createDirectoryAtPath:[path stringByDeletingLastPathComponent]
                              withIntermediateDirectories:YES attributes:nil error:nil];
    NSError* werr = nil;
    if (![png writeToFile:path options:NSDataWritingAtomic error:&werr])
        return [NSString stringWithFormat:@"ERROR: write failed: %@", werr.localizedDescription ?: @"unknown"];

    return [NSString stringWithFormat:@"OK: %@ (%dx%d, window \"%@\")",
            path, (int)rep.pixelsWide, (int)rep.pixelsHigh, target.title];
}

static NSString* SnapshotByTitle( NSString* title, NSRect region, CGFloat scale, NSString* path )
{
    __block NSString* outcome = @"ERROR: unknown";
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil)
        {
            outcome = [NSString stringWithFormat:@"ERROR: no visible window%@",
                       title.length ? [NSString stringWithFormat:@" matching \"%@\"", title] : @""];
            return;
        }
        outcome = SnapshotWindowCore( target, region, scale, path );
    } );
    return outcome;
}

// ---- web viewer capture -----------------------------------------------------------------

static void CollectWebViews( NSView* v, NSMutableArray<WKWebView*>* into )
{
    if ([v isKindOfClass:[WKWebView class]]) [into addObject:(WKWebView*)v];
    for (NSView* sub in v.subviews) CollectWebViews( sub, into );
}

static NSString* WebViewerSnapshot( NSString* title, NSInteger index, NSString* path )
{
    __block NSString* outcome = @"ERROR: unknown";
    __block WKWebView* web = nil;
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil) { outcome = @"ERROR: no matching visible window"; return; }
        NSMutableArray<WKWebView*>* views = [NSMutableArray array];
        CollectWebViews( target.contentView, views );
        if ((NSUInteger)index >= views.count)
        {
            outcome = [NSString stringWithFormat:@"ERROR: window has %lu web viewer(s), index %ld out of range",
                       (unsigned long)views.count, (long)index];
            return;
        }
        web = views[(NSUInteger)index];
        outcome = nil; // signals "proceed"
    } );
    if (outcome != nil) return outcome;

    // WKWebView snapshots are async; pump the run loop (we are on FileMaker's
    // main thread when called from a calc) until completion or timeout.
    __block NSString* result = nil;
    RunOnMain( ^{
        WKSnapshotConfiguration* cfg = [WKSnapshotConfiguration new];
        [web takeSnapshotWithConfiguration:cfg completionHandler:^(NSImage* img, NSError* err) {
            if (img == nil)
            {
                result = [NSString stringWithFormat:@"ERROR: snapshot failed: %@",
                          err.localizedDescription ?: @"unknown"];
                return;
            }
            NSBitmapImageRep* rep = [[NSBitmapImageRep alloc] initWithData:img.TIFFRepresentation];
            NSData* png = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
            if (png == nil) { result = @"ERROR: PNG encoding failed"; return; }
            [[NSFileManager defaultManager] createDirectoryAtPath:[path stringByDeletingLastPathComponent]
                                      withIntermediateDirectories:YES attributes:nil error:nil];
            NSError* werr = nil;
            if (![png writeToFile:path options:NSDataWritingAtomic error:&werr])
            {
                result = [NSString stringWithFormat:@"ERROR: write failed: %@",
                          werr.localizedDescription ?: @"unknown"];
                return;
            }
            result = [NSString stringWithFormat:@"OK: %@ (%dx%d, web viewer)",
                      path, (int)rep.pixelsWide, (int)rep.pixelsHigh];
        }];
    } );

    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:5.0];
    while (result == nil && [deadline timeIntervalSinceNow] > 0)
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                 beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    return result ?: @"ERROR: snapshot timed out (5s)";
}

// Enumerate the web viewers in a window so an agent can pick a snapshot index.
static NSString* WebViewerListJSON( NSString* title )
{
    __block NSString* json = @"[]";
    __block NSString* err = nil;
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil) { err = @"ERROR: no matching visible window"; return; }
        NSMutableArray* arr = [NSMutableArray array];
        NSMutableArray<WKWebView*>* views = [NSMutableArray array];
        CollectWebViews( target.contentView, views );
        [views enumerateObjectsUsingBlock:^(WKWebView* w, NSUInteger i, BOOL*) {
            [arr addObject:@{
                @"index":   @(i),
                @"url":     w.URL.absoluteString ?: @"",
                @"title":   w.title ?: @"",
                @"loading": @(w.isLoading),
                @"width":   @((int)w.frame.size.width),
                @"height":  @((int)w.frame.size.height),
            }];
        }];
        json = JSONString( arr );
    } );
    return err ?: json;
}

// ---- clipboard: FileMaker XML flavors ---------------------------------------------------

// FileMaker's Mac clipboard flavors are classic four-char OSTypes. The reliable,
// deterministic pasteboard type string for one is the legacy bridge form
// "CorePasteboardFlavorType 0x<hex>" — reading and writing it round-trips with
// the dyn.* UTI FileMaker itself advertises (verified against FM 26; the
// deprecated UTTypeCreatePreferredIdentifierForTag derivation returns a short
// dyn form FileMaker does NOT use).
static NSString* FlavorForFMCode( NSString* code )
{
    if (code.length != 4) return nil;
    const char* c = code.UTF8String;
    return [NSString stringWithFormat:@"CorePasteboardFlavorType 0x%02X%02X%02X%02X",
            c[0], c[1], c[2], c[3]];
}

// Decode "CorePasteboardFlavorType 0x584D5353" back to "XMSS" (nil if not that shape).
static NSString* FMCodeFromFlavorType( NSString* type )
{
    NSString* prefix = @"CorePasteboardFlavorType 0x";
    if (![type hasPrefix:prefix] || type.length != prefix.length + 8) return nil;
    unsigned value = 0;
    if (![[NSScanner scannerWithString:[type substringFromIndex:prefix.length]] scanHexInt:&value]) return nil;
    char c[5] = { (char)(value >> 24), (char)(value >> 16), (char)(value >> 8), (char)value, 0 };
    for (int i = 0; i < 4; i++) if (c[i] < 0x20 || c[i] > 0x7E) return nil;
    return @(c);
}

static NSDictionary<NSString*, NSString*>* FMClipboardCodes( void )
{
    // code -> what it carries
    return @{
        @"XMTB": @"tables",
        @"XMFD": @"fields",
        @"XMSC": @"scripts",
        @"XMSS": @"script steps",
        @"XML2": @"layout objects",
        @"XMLO": @"layout objects (legacy)",
        @"XMVL": @"value lists",
        @"XMFN": @"custom functions",
    };
}

static NSString* XMLFromClipboardData( NSData* data )
{
    if (data.length == 0) return nil;
    const uint8_t* bytes = (const uint8_t*)data.bytes;
    // plain UTF-8 XML
    if (bytes[0] == '<')
        return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    // UTF-16 BOM
    if (data.length >= 2 && ((bytes[0] == 0xFF && bytes[1] == 0xFE) || (bytes[0] == 0xFE && bytes[1] == 0xFF)))
        return [[NSString alloc] initWithData:data encoding:NSUTF16StringEncoding];
    // 4-byte length prefix (Windows-style payloads travel sometimes)
    if (data.length > 4 && bytes[4] == '<')
        return [[NSString alloc] initWithData:[data subdataWithRange:NSMakeRange( 4, data.length - 4 )]
                                     encoding:NSUTF8StringEncoding];
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}

// Guess the FM flavor for a snippet by its first child element. Order matters:
// scripts contain steps, layouts contain fields.
static NSString* SniffFMCode( NSString* xml )
{
    NSArray* probes = @[
        @[@"<Layout",         @"XML2"],
        @[@"<Script",         @"XMSC"],
        @[@"<Step",           @"XMSS"],
        @[@"<ValueList",      @"XMVL"],
        @[@"<CustomFunction", @"XMFN"],
        @[@"<BaseTable",      @"XMTB"],
        @[@"<Field",          @"XMFD"],
    ];
    for (NSArray* p in probes)
        if ([xml containsString:p[0]]) return p[1];
    return nil;
}

static NSString* ClipboardFormatsJSON( void )
{
    __block NSString* json = @"[]";
    RunOnMain( ^{
        NSMutableArray* arr = [NSMutableArray array];
        NSDictionary* codes = FMClipboardCodes();
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        for (NSPasteboardType t in pb.types)
        {
            NSMutableDictionary* entry = [@{ @"uti": t } mutableCopy];
            NSString* code = FMCodeFromFlavorType( t );
            if (code)
            {
                entry[@"fmCode"] = code;
                entry[@"carries"] = codes[code] ?: @"unknown four-char flavor";
            }
            [arr addObject:entry];
        }
        json = JSONString( arr );
    } );
    return json;
}

static NSString* ClipboardGetXML( NSString* code )
{
    __block NSString* out = @"ERROR: no FileMaker XML on the clipboard";
    RunOnMain( ^{
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        if (code.length)
        {
            NSString* flavor = FlavorForFMCode( code );
            NSData* d = flavor ? [pb dataForType:flavor] : nil;
            NSString* xml = d.length ? XMLFromClipboardData( d ) : nil;
            out = xml.length ? xml
                : [NSString stringWithFormat:@"ERROR: no clipboard data for FileMaker flavor %@", code];
            return;
        }
        // no code given: any four-char CorePasteboardFlavorType on the board counts,
        // known to the table or not
        for (NSPasteboardType t in pb.types)
        {
            if (FMCodeFromFlavorType( t ) == nil) continue;
            NSData* d = [pb dataForType:t];
            if (d.length)
            {
                NSString* xml = XMLFromClipboardData( d );
                if (xml.length) { out = xml; return; }
            }
        }
    } );
    return out;
}

static NSString* ClipboardSetXML( NSString* xml, NSString* code )
{
    NSString* useCode = code.length ? code : SniffFMCode( xml );
    if (useCode.length == 0)
        return @"ERROR: could not infer the FileMaker flavor; pass a code (XMSS, XMSC, XML2, XMTB, XMFD, XMVL, XMFN)";
    NSString* flavor = FlavorForFMCode( useCode );
    if (flavor == nil) return @"ERROR: flavor code must be 4 characters (e.g. XMSS)";

    __block NSString* out;
    RunOnMain( ^{
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        [pb clearContents];
        [pb declareTypes:@[flavor] owner:nil];
        BOOL ok = [pb setData:[xml dataUsingEncoding:NSUTF8StringEncoding] forType:flavor];
        out = ok ? [NSString stringWithFormat:@"OK: %lu bytes on clipboard as %@ (%@)",
                    (unsigned long)[xml lengthOfBytesUsingEncoding:NSUTF8StringEncoding],
                    useCode, FMClipboardCodes()[useCode] ?: @"?"]
                 : @"ERROR: pasteboard write failed";
    } );
    return out;
}

// ---- state probe ------------------------------------------------------------------------

// which FileMaker copy hosts this plug-in (defined with the auto-arm code below)
static NSString* HostAppName( void );

// command-channel state, declared here so the state probe can report it
static NSString* gChannelFolder = nil;
static BOOL      gChannelActive = NO;
static NSUInteger gChannelProcessed = 0;
static NSString* gChannelLastError = nil;

// auto-arm (0.4.0): idle reads ~/.fm-lens/config.json and arms the channel
// for an allowlisted frontmost file with no script run. The config file is the
// opt-in. An explicit FMLens_ChannelStop suppresses auto-arm until the config
// file's mtime changes (re-consent) or FileMaker restarts.
static NSTimeInterval gAutoArmLastCheck = 0;           // throttle: stat config at most every few sec
static NSTimeInterval gAutoArmSuppressMtime = 0;       // config mtime at which a manual stop was issued
static BOOL      gChannelAutoArmed = NO;               // reported in state/status
static NSString* gChannelFile = nil;                   // the file an auto-arm was for

static NSString* StateJSON( const fmx::ExprEnv& env )
{
    NSDictionary* probes = @{
        @"file":            @"Get ( FileName )",
        @"layout":          @"Get ( LayoutName )",
        @"layoutNumber":    @"Get ( LayoutNumber )",
        @"table":           @"Get ( LayoutTableName )",
        @"window":          @"Get ( WindowName )",
        @"windowMode":      @"Get ( WindowMode )",
        @"foundCount":      @"Get ( FoundCount )",
        @"totalRecords":    @"Get ( TotalRecordCount )",
        @"recordsOpen":     @"Get ( RecordOpenCount )",
        @"lastError":       @"Get ( LastError )",
        @"scriptRunning":   @"Get ( ScriptName )",
        @"account":         @"Get ( AccountName )",
        @"appVersion":      @"Get ( ApplicationVersion )",
    };
    NSMutableDictionary* out = [NSMutableDictionary dictionary];
    for (NSString* key in probes)
    {
        NSString* v = EvalExpr( env, probes[key] );
        out[key] = v ?: @"?";
    }
    out[@"helper"] = @(kVersionString);

    // wedge diagnostics: a modal dialog or sheet explains dead triggers,
    // callback timeouts, and idleState "unsafe" better than any log
    RunOnMain( ^{
        NSWindow* modal = [NSApp modalWindow];
        out[@"modalWindow"] = modal
            ? (modal.title.length ? modal.title : NSStringFromClass( modal.class ))
            : @"";
        NSMutableArray* sheets = [NSMutableArray array];
        for (NSWindow* w in [NSApp orderedWindows])
            if (w.attachedSheet != nil && w.title.length)
                [sheets addObject:w.title];
        out[@"sheetsOn"] = sheets;
        out[@"keyWindowClass"] = [NSApp keyWindow]
            ? NSStringFromClass( [NSApp keyWindow].class ) : @"";
    } );
    out[@"channelActive"] = @(gChannelActive);
    out[@"channelFolder"] = gChannelFolder ?: @"";
    out[@"channelAutoArmed"] = @(gChannelAutoArmed);
    out[@"hostApp"] = HostAppName();
    return JSONString( out );
}

// ---- script starting --------------------------------------------------------------------

static FMX_ScriptControl ScriptControlFromString( NSString* s )
{
    NSString* c = s.lowercaseString;
    if ([c isEqualToString:@"halt"])   return kFMXT_Halt;
    if ([c isEqualToString:@"exit"])   return kFMXT_Exit;
    if ([c isEqualToString:@"pause"])  return kFMXT_Pause;
    return kFMXT_Resume;
}

static NSString* StartScript( NSString* fileName, NSString* scriptName, NSString* param, NSString* control )
{
    if (fileName.length == 0 || scriptName.length == 0)
        return @"ERROR: fileName and scriptName are required";

    fmx::TextUniquePtr fileT, scriptT;
    AssignFMXText( *fileT, fileName );
    AssignFMXText( *scriptT, scriptName );

    fmx::DataUniquePtr paramD;
    if (param.length)
    {
        fmx::TextUniquePtr paramT;
        AssignFMXText( *paramT, param );
        paramD->SetAsText( *paramT, paramD->GetLocale() );
    }

    const FMX_ErrorCode err = FMX_StartScript( &(*fileT), &(*scriptT),
                                               ScriptControlFromString( control ),
                                               param.length ? &(*paramD) : nullptr );
    if (err != 0)
        return [NSString stringWithFormat:@"ERROR: StartScript failed (%d)", (int)err];
    return [NSString stringWithFormat:@"OK: queued \"%@\" in \"%@\"", scriptName, fileName];
}

// ---- command channel --------------------------------------------------------------------
//
// FMLens_ChannelStart( folder ) arms an idle-loop worker: the agent drops
// <anything>.json command files into the folder; the plug-in executes each and
// writes results/<same-name>, then moves the command to processed/. The channel
// is off until a calc inside FileMaker arms it (typically an OnFirstWindowOpen
// script), so no standing execution surface exists without an opt-in.

static NSString* ChannelStart( NSString* folder )
{
    if (folder.length == 0) return @"ERROR: folder path required";
    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSError* err = nil;
    for (NSString* sub in @[@"", @"results", @"processed"])
    {
        NSString* p = sub.length ? [folder stringByAppendingPathComponent:sub] : folder;
        if (![fmgr createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:&err])
            return [NSString stringWithFormat:@"ERROR: cannot create %@: %@", p, err.localizedDescription];
    }
    gChannelFolder = [folder copy];
    gChannelActive = YES;
    gChannelProcessed = 0;
    gChannelLastError = nil;
    return [NSString stringWithFormat:@"OK: channel armed at %@", folder];
}

static NSString* ChannelStatusJSON( void )
{
    return JSONString( @{
        @"active":    @(gChannelActive),
        @"folder":    gChannelFolder ?: @"",
        @"processed": @(gChannelProcessed),
        @"lastError": gChannelLastError ?: @"",
        @"autoArmed": @(gChannelAutoArmed),
        @"hostApp":   HostAppName(),
        @"helper":    @(kVersionString),
    } );
}

// Auto-arm: consult ~/.fm-lens/config.json on idle and, if it opts in and
// names the frontmost file, arm the channel with no script run. The config
// file's existence + autoArm:true IS the standing consent; without it nothing
// arms. A manual FMLens_ChannelStop records the config mtime so auto-arm stays
// off until the user edits the config again (re-consent) or FileMaker restarts.
// ~/.fm-lens is the root for config and channel folders (0.5.0). A machine
// that only has the ADT Helper-era ~/.adt-helper/config.json keeps its consent:
// that file is read until a ~/.fm-lens/config.json exists.
static NSString* LensRoot( void )
{
    return [NSHomeDirectory() stringByAppendingPathComponent:@".fm-lens"];
}

static NSString* AutoArmConfigPath( void )
{
    NSString* current = [LensRoot() stringByAppendingPathComponent:@"config.json"];
    NSString* legacy  = [NSHomeDirectory() stringByAppendingPathComponent:@".adt-helper/config.json"];
    NSFileManager* fmgr = [NSFileManager defaultManager];
    if (![fmgr fileExistsAtPath:current] && [fmgr fileExistsAtPath:legacy]) return legacy;
    return current;
}

// Which FileMaker copy is hosting this plug-in — "FileMaker Pro",
// "FileMaker Pro Agent", … Joe runs duplicated FileMaker apps as independent
// clients, and they SHARE the version-keyed Extensions folder, so one plug-in
// binary is loaded by every copy. Auto-arm is scoped by this name so an
// agent-owned copy can arm itself while the human's copy never does.
static NSString* HostAppName( void )
{
    NSString* p = [[NSBundle mainBundle] bundlePath];
    if (p.length == 0) return [[NSProcessInfo processInfo] processName] ?: @"";
    return [[p lastPathComponent] stringByDeletingPathExtension];
}

static void AutoArmIdleCheck( const fmx::ExprEnv& env )
{
    if (gChannelActive) return;                      // already armed (manually or earlier)

    // throttle: stat the config at most ~every 3s, not every idle tick
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - gAutoArmLastCheck < 3.0) return;
    gAutoArmLastCheck = now;

    NSString* cfgPath = AutoArmConfigPath();
    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSDictionary* attrs = [fmgr attributesOfItemAtPath:cfgPath error:nil];
    if (!attrs) return;                              // no config → no standing consent → nothing arms
    NSTimeInterval cfgMtime = [(NSDate*)attrs[NSFileModificationDate] timeIntervalSinceReferenceDate];

    // a manual stop suppresses auto-arm until the config is touched again
    if (gAutoArmSuppressMtime != 0 && cfgMtime <= gAutoArmSuppressMtime) return;

    NSData* raw = [NSData dataWithContentsOfFile:cfgPath];
    NSDictionary* cfg = raw.length ? [NSJSONSerialization JSONObjectWithData:raw options:0 error:nil] : nil;
    if (![cfg isKindOfClass:[NSDictionary class]]) return;

    // per-app scoping (0.4.1): an "apps" map keyed by the host app's name
    // overrides the top-level keys for THIS copy of FileMaker. A copy with
    // {"autoArm": false} never arms, which is how the human's copy stays out
    // of the agent's way while both share one plug-in binary.
    NSString* host = HostAppName();
    NSDictionary* apps = [cfg[@"apps"] isKindOfClass:[NSDictionary class]] ? cfg[@"apps"] : nil;
    NSDictionary* mine = [apps[host] isKindOfClass:[NSDictionary class]] ? apps[host] : nil;

    id armVal = (mine && mine[@"autoArm"] != nil) ? mine[@"autoArm"] : cfg[@"autoArm"];
    if (![armVal respondsToSelector:@selector(boolValue)] || ![armVal boolValue]) return;

    // which file is frontmost IN THIS PROCESS right now?
    NSString* frontFile = EvalExpr( env, @"Get ( FileName )" );
    if (frontFile.length == 0) return;

    // allowlist: files[] must name it (a "*" entry allows any open file)
    id filesVal = (mine && mine[@"files"] != nil) ? mine[@"files"] : cfg[@"files"];
    NSArray* files = [filesVal isKindOfClass:[NSArray class]] ? filesVal : @[];
    BOOL allowed = NO;
    for (id f in files)
        if ([f isKindOfClass:[NSString class]] && ([f isEqualToString:@"*"] || [f isEqualToString:frontFile]))
            { allowed = YES; break; }
    if (!allowed) return;

    // folder: explicit override wins; otherwise namespace by host app so two
    // copies with the SAME file open never race for one command queue —
    // ~/.fm-lens/<app>/<file>
    id folderVal = (mine && mine[@"folder"] != nil) ? mine[@"folder"] : cfg[@"folder"];
    NSString* folder = [folderVal isKindOfClass:[NSString class]] && [folderVal length]
        ? folderVal
        : [[LensRoot() stringByAppendingPathComponent:host]
                stringByAppendingPathComponent:frontFile];

    NSString* r = ChannelStart( folder );
    gChannelAutoArmed = [r hasPrefix:@"OK"];
    gChannelFile = gChannelAutoArmed ? [frontFile copy] : nil;
    if (!gChannelAutoArmed) gChannelLastError = r;
}

// ---- UI control (0.5.0): Cocoa only, no FileMaker calc environment -----------------------
//
// Everything here drives FileMaker's own UI from inside its process: menus,
// dialogs, windows. None of it touches the calc engine, so it is safe to run
// from the app-level channel's timer even while a modal dialog has stopped
// FileMaker's idle calls. Nothing here types into a field.

static NSString* MenuTitleKey( NSString* t )
{
    NSString* s = [t stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
    if ([s hasSuffix:@"…"]) s = [s substringToIndex:s.length - 1];
    if ([s hasSuffix:@"..."]) s = [s substringToIndex:s.length - 3];
    return s.lowercaseString;
}

static void RefreshMenu( NSMenu* menu )
{
    if ([menu.delegate respondsToSelector:@selector(menuNeedsUpdate:)])
        [menu.delegate menuNeedsUpdate:menu];
    [menu update];
}

// Walk the main menu by titles, e.g. @[@"Records", @"New Record"].
static NSMenuItem* FindMenuItem( NSArray<NSString*>* path, NSString** why )
{
    NSMenu* menu = [NSApp mainMenu];
    NSMenuItem* found = nil;
    for (NSUInteger depth = 0; depth < path.count; depth++)
    {
        if (menu == nil) { *why = @"menu path is deeper than the menus"; return nil; }
        RefreshMenu( menu );
        NSString* want = MenuTitleKey( path[depth] );
        found = nil;
        for (NSMenuItem* item in menu.itemArray)
            if (!item.isSeparatorItem && [MenuTitleKey( item.title ) isEqualToString:want]) { found = item; break; }
        if (found == nil)
        {
            NSMutableArray* titles = [NSMutableArray array];
            for (NSMenuItem* item in menu.itemArray)
                if (!item.isSeparatorItem && item.title.length) [titles addObject:item.title];
            *why = [NSString stringWithFormat:@"no menu item \"%@\"; available: %@",
                    path[depth], [titles componentsJoinedByString:@" | "]];
            return nil;
        }
        menu = found.submenu;
    }
    return found;
}

static NSString* PerformMenu( NSArray<NSString*>* path )
{
    if (path.count == 0) return @"ERROR: menu path required, e.g. [\"Records\",\"New Record\"]";
    __block NSString* out = nil;
    RunOnMain( ^{
        NSString* why = nil;
        NSMenuItem* item = FindMenuItem( path, &why );
        if (item == nil) { out = [@"ERROR: " stringByAppendingString:why]; return; }
        if (item.hasSubmenu) { out = @"ERROR: that item opens a submenu; name one of its items"; return; }
        NSMenu* parent = item.menu;
        RefreshMenu( parent );
        if (!item.isEnabled)
        {
            out = [NSString stringWithFormat:@"ERROR: \"%@\" is disabled right now (wrong mode, no window, or a dialog is up)", item.title];
            return;
        }
        [parent performActionForItemAtIndex:[parent indexOfItem:item]];
        out = [NSString stringWithFormat:@"OK: performed %@", [path componentsJoinedByString:@" > "]];
    } );
    return out;
}

// View > Go to Layout > <name>. No script start, so no 825 (quirk 105).
static NSString* GoToLayout( NSString* layout )
{
    if (layout.length == 0) return @"ERROR: layout name required";
    __block NSArray<NSString*>* path = nil;
    __block NSString* why = nil;
    RunOnMain( ^{
        NSString* err = nil;
        NSMenuItem* view = FindMenuItem( @[@"View"], &err );
        if (view.submenu == nil) { why = err ?: @"no View menu"; return; }
        RefreshMenu( view.submenu );
        for (NSMenuItem* item in view.submenu.itemArray)
        {
            if (!item.hasSubmenu || ![MenuTitleKey( item.title ) hasPrefix:@"go to layout"]) continue;
            RefreshMenu( item.submenu );
            NSMutableArray* names = [NSMutableArray array];
            for (NSMenuItem* li in item.submenu.itemArray)
            {
                if (li.isSeparatorItem || li.title.length == 0) continue;
                [names addObject:li.title];
                if ([li.title isEqualToString:layout]) { path = @[view.title, item.title, li.title]; return; }
            }
            why = [NSString stringWithFormat:@"no layout \"%@\" in View > %@; available: %@",
                   layout, item.title, [names componentsJoinedByString:@" | "]];
            return;
        }
        why = @"no \"Go to Layout\" submenu under View (a custom menu set may have removed it)";
    } );
    if (path == nil) return [@"ERROR: " stringByAppendingString:why ?: @"unknown"];
    return PerformMenu( path );
}

static NSString* SetMode( NSString* mode )
{
    NSDictionary* titles = @{ @"browse": @"Browse Mode", @"find": @"Find Mode",
                              @"layout": @"Layout Mode", @"preview": @"Preview Mode" };
    NSString* title = titles[mode.lowercaseString];
    if (title == nil) return @"ERROR: mode must be browse, find, layout or preview";
    return PerformMenu( @[@"View", title] );
}

static void CollectControls( NSView* v, NSMutableArray* texts, NSMutableArray* buttons, NSMutableArray* fields )
{
    if (v.isHidden) return;
    if ([v isKindOfClass:[NSButton class]])
    {
        NSButton* b = (NSButton*)v;
        if (b.title.length) [buttons addObject:@{ @"title": b.title, @"enabled": @(b.isEnabled) }];
    }
    else if ([v isKindOfClass:[NSTextField class]])
    {
        NSTextField* t = (NSTextField*)v;
        if (t.isEditable)
            [fields addObject:@{ @"secure": @([t isKindOfClass:[NSSecureTextField class]]),
                                 @"placeholder": t.placeholderString ?: @"" }];
        else if (t.stringValue.length)
            [texts addObject:t.stringValue];
    }
    for (NSView* sub in v.subviews) CollectControls( sub, texts, buttons, fields );
}

// Modal windows, sheets and visible panels: the things that stop FileMaker's idle loop.
static NSArray<NSWindow*>* DialogWindows( void )
{
    NSMutableArray<NSWindow*>* out = [NSMutableArray array];
    NSWindow* modal = [NSApp modalWindow];
    if (modal) [out addObject:modal];
    for (NSWindow* w in [NSApp windows])
    {
        if (!w.isVisible) continue;
        if (w.attachedSheet && ![out containsObject:w.attachedSheet]) [out addObject:w.attachedSheet];
        if ([w isKindOfClass:[NSPanel class]] && w.isSheet == NO && ![out containsObject:w]
            && (w.styleMask & NSWindowStyleMaskTitled) && [(NSPanel*)w worksWhenModal] == NO
            && w.level >= NSModalPanelWindowLevel)
            [out addObject:w];
    }
    return out;
}

static NSArray* DialogsInfo( void )
{
    __block NSMutableArray* arr = [NSMutableArray array];
    RunOnMain( ^{
        NSWindow* modal = [NSApp modalWindow];
        for (NSWindow* w in DialogWindows())
        {
            NSMutableArray* texts = [NSMutableArray array], *buttons = [NSMutableArray array],
                           *fields = [NSMutableArray array];
            CollectControls( w.contentView, texts, buttons, fields );
            [arr addObject:@{ @"title": w.title ?: @"", @"class": NSStringFromClass( w.class ),
                              @"modal": @(w == modal), @"sheet": @(w.isSheet),
                              @"texts": texts, @"buttons": buttons, @"fields": fields }];
        }
    } );
    return arr;
}

static NSButton* FindButton( NSView* v, NSString* title )
{
    if (v.isHidden) return nil;
    if ([v isKindOfClass:[NSButton class]]
        && [MenuTitleKey( ((NSButton*)v).title ) isEqualToString:MenuTitleKey( title )])
        return (NSButton*)v;
    for (NSView* sub in v.subviews)
        if (NSButton* b = FindButton( sub, title )) return b;
    return nil;
}

// Press a button on a dialog. Pressing is all it does: it never fills a field,
// so a sign-in prompt can be cancelled but never answered.
static NSString* DialogPress( NSString* button, NSString* dialogTitle )
{
    if (button.length == 0) return @"ERROR: button title required";
    __block NSString* out = nil;
    RunOnMain( ^{
        for (NSWindow* w in DialogWindows())
        {
            if (dialogTitle.length && ![w.title localizedCaseInsensitiveContainsString:dialogTitle]) continue;
            NSButton* b = FindButton( w.contentView, button );
            if (b == nil) continue;
            if (!b.isEnabled) { out = [NSString stringWithFormat:@"ERROR: \"%@\" is disabled", b.title]; return; }
            [b performClick:nil];
            out = [NSString stringWithFormat:@"OK: pressed \"%@\" on \"%@\"", b.title, w.title];
            return;
        }
        out = [NSString stringWithFormat:@"ERROR: no open dialog%@ has a \"%@\" button",
               dialogTitle.length ? [NSString stringWithFormat:@" titled \"%@\"", dialogTitle] : @"", button];
    } );
    return out;
}

// Close one window of THIS FileMaker copy. Exact title first, then a contains match.
static NSString* CloseWindow( NSString* title )
{
    if (title.length == 0) return @"ERROR: window title required";
    __block NSString* out = nil;
    RunOnMain( ^{
        NSWindow* hit = nil;
        for (NSWindow* w in [NSApp orderedWindows])
            if (w.isVisible && [w.title isEqualToString:title]) { hit = w; break; }
        if (hit == nil) hit = FindWindow( title );
        if (hit == nil) { out = [NSString stringWithFormat:@"ERROR: no visible window matching \"%@\"", title]; return; }
        NSString* closed = hit.title;
        [hit performClose:nil];
        out = [NSString stringWithFormat:@"OK: asked \"%@\" to close", closed];
    } );
    return out;
}

// Open a file in THIS FileMaker copy, addressed by bundle path rather than
// bundle id, so it can never land in another copy (quirk 70).
static NSString* OpenFile( NSString* path )
{
    if (path.length == 0) return @"ERROR: path required";
    NSString* full = path.stringByExpandingTildeInPath;
    if (![[NSFileManager defaultManager] fileExistsAtPath:full])
        return [NSString stringWithFormat:@"ERROR: no file at %@", full];
    RunOnMain( ^{
        NSWorkspaceOpenConfiguration* cfg = [NSWorkspaceOpenConfiguration configuration];
        cfg.activates = YES;
        [[NSWorkspace sharedWorkspace] openURLs:@[[NSURL fileURLWithPath:full]]
                           withApplicationAtURL:[[NSBundle mainBundle] bundleURL]
                                  configuration:cfg completionHandler:nil];
    } );
    return [NSString stringWithFormat:@"OK: asked %@ to open %@ (watch windowlist/dialogs for the result)", HostAppName(), full];
}

static NSArray* WindowListInfo( void )
{
    __block NSMutableArray* arr = [NSMutableArray array];
    RunOnMain( ^{
        for (NSWindow* w in [NSApp orderedWindows])
        {
            if (w.title.length == 0 && !w.isVisible) continue;
            [arr addObject:@{ @"title": w.title ?: @"", @"visible": @(w.isVisible),
                              @"main": @(w.isMainWindow), @"key": @(w.isKeyWindow),
                              @"miniaturized": @(w.isMiniaturized),
                              @"sheet": @(w.attachedSheet != nil),
                              @"class": NSStringFromClass( w.class ),
                              @"width": @((int)w.frame.size.width),
                              @"height": @((int)w.frame.size.height) }];
        }
    } );
    return arr;
}

static id ParsedJSON( NSString* s )
{
    NSData* d = [s dataUsingEncoding:NSUTF8StringEncoding];
    id obj = d ? [NSJSONSerialization JSONObjectWithData:d options:0 error:nil] : nil;
    return obj ?: s;
}

static NSDictionary* Outcome( NSString* r )
{
    return [r hasPrefix:@"ERROR"] ? @{ @"ok": @NO, @"error": r } : @{ @"ok": @YES, @"result": r };
}

static NSArray<NSString*>* StringArray( id v )
{
    if (![v isKindOfClass:[NSArray class]]) return nil;
    for (id x in (NSArray*)v) if (![x isKindOfClass:[NSString class]]) return nil;
    return v;
}

// Window snapshot with a structured result: path, width, height, bytes.
static NSDictionary* SnapshotCommand( NSDictionary* cmd, NSRect region )
{
    NSString* path = [cmd[@"path"] isKindOfClass:[NSString class]] ? cmd[@"path"] : @"";
    if (path.length == 0) return @{ @"ok": @NO, @"error": @"path required" };
    NSString* window = [cmd[@"window"] isKindOfClass:[NSString class]] ? cmd[@"window"] : @"";
    CGFloat scale = cmd[@"scale"] ? [cmd[@"scale"] doubleValue] : 0;
    NSString* r = SnapshotByTitle( window, region, scale, path );
    if (![r hasPrefix:@"OK"]) return @{ @"ok": @NO, @"error": r };
    NSDictionary* attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:path error:nil];
    NSImageRep* rep = [NSImageRep imageRepWithContentsOfFile:path];
    return @{ @"ok": @YES, @"result": @{
        @"message": r, @"path": path,
        @"bytes": attrs[NSFileSize] ?: @0,
        @"width": @(rep.pixelsWide), @"height": @(rep.pixelsHigh) } };
}

// Commands that need no calc environment. nil means "not a UI command".
static NSDictionary* ExecuteUICommand( NSDictionary* cmd )
{
    NSString* verb = [cmd[@"cmd"] isKindOfClass:[NSString class]] ? cmd[@"cmd"] : @"";
    NSString* (^S)(NSString*) = ^NSString*( NSString* key ) {
        id v = cmd[key];
        return [v isKindOfClass:[NSString class]] ? v : @"";
    };

    if ([verb isEqualToString:@"version"])
        return @{ @"ok": @YES, @"result": @(kVersionString) };
    if ([verb isEqualToString:@"windowlist"])
        return @{ @"ok": @YES, @"result": WindowListInfo() };
    if ([verb isEqualToString:@"dialogs"])
        return @{ @"ok": @YES, @"result": DialogsInfo() };
    if ([verb isEqualToString:@"dialog-press"])
        return Outcome( DialogPress( S( @"button" ), S( @"dialog" ) ) );
    if ([verb isEqualToString:@"menu"])
    {
        NSArray<NSString*>* path = StringArray( cmd[@"path"] );
        if (path == nil) return @{ @"ok": @NO, @"error": @"path must be an array of menu titles" };
        return Outcome( PerformMenu( path ) );
    }
    if ([verb isEqualToString:@"gotolayout"])
        return Outcome( GoToLayout( S( @"layout" ) ) );
    if ([verb isEqualToString:@"mode"])
        return Outcome( SetMode( S( @"mode" ) ) );
    if ([verb isEqualToString:@"newrecord"])
        return Outcome( PerformMenu( @[@"Records", @"New Record"] ) );
    if ([verb isEqualToString:@"closewindow"])
        return Outcome( CloseWindow( S( @"window" ) ) );
    if ([verb isEqualToString:@"openfile"])
        return Outcome( OpenFile( S( @"path" ) ) );
    if ([verb isEqualToString:@"snapshot"] && cmd[@"object"] == nil)
    {
        NSRect region = NSZeroRect;
        if (cmd[@"w"] && cmd[@"h"])
            region = NSMakeRect( [cmd[@"x"] doubleValue], [cmd[@"y"] doubleValue],
                                 [cmd[@"w"] doubleValue], [cmd[@"h"] doubleValue] );
        return SnapshotCommand( cmd, region );
    }
    if ([verb isEqualToString:@"webviewerlist"])
    {
        NSString* r = WebViewerListJSON( S( @"window" ) );
        return [r hasPrefix:@"ERROR"] ? @{ @"ok": @NO, @"error": r } : @{ @"ok": @YES, @"result": ParsedJSON( r ) };
    }
    if ([verb isEqualToString:@"clipboard-formats"])
        return @{ @"ok": @YES, @"result": ParsedJSON( ClipboardFormatsJSON() ) };
    if ([verb isEqualToString:@"clipboard-get"])
        return Outcome( ClipboardGetXML( S( @"code" ) ) );
    if ([verb isEqualToString:@"clipboard-set"])
    {
        NSString* xml = S( @"xml" );
        if (xml.length == 0) return @{ @"ok": @NO, @"error": @"xml required" };
        return Outcome( ClipboardSetXML( xml, S( @"code" ) ) );
    }
    return nil;
}

static NSString* const kHelpText =
    @"UI (both channels): version | windowlist | dialogs | dialog-press {button, dialog?} | "
     "menu {path:[...]} | gotolayout {layout} | mode {mode: browse|find|layout|preview} | newrecord | "
     "closewindow {window} | openfile {path} | snapshot {path, window?, x/y/w/h?, scale?} | "
     "webviewerlist {window?} | clipboard-formats | clipboard-get {code?} | clipboard-set {xml, code?}. "
     "File channel only: state | evaluate {expr} | sql {query, file?} | "
     "runscript {script, file?, param?, control?} | snapshot {path, object, window?, scale?} | "
     "websnapshot {path, window?, index?} | help";

// Snapshot of one named layout object, located with GetLayoutObjectAttribute.
static NSDictionary* ObjectSnapshot( NSDictionary* cmd, const fmx::ExprEnv& env )
{
    NSString* name = [cmd[@"object"] isKindOfClass:[NSString class]] ? cmd[@"object"] : @"";
    if (name.length == 0) return @{ @"ok": @NO, @"error": @"object name required" };
    NSString* quoted = [[name stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"]
                              stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
    NSString* bounds = EvalExpr( env, [NSString stringWithFormat:
                                       @"GetLayoutObjectAttribute ( \"%@\" ; \"bounds\" )", quoted] );
    NSArray* parts = [[bounds stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]]
                         componentsSeparatedByCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
    NSMutableArray* nums = [NSMutableArray array];
    for (NSString* p in parts) if (p.length) [nums addObject:@(p.doubleValue)];
    if (nums.count < 4)
        return @{ @"ok": @NO, @"error": [NSString stringWithFormat:
                  @"no named object \"%@\" on the current layout (GetLayoutObjectAttribute bounds: \"%@\")",
                  name, bounds ?: @"?"] };

    // bounds are window coordinates below the status toolbar; the snapshot view
    // includes the toolbar, so shift down by the difference in heights.
    NSString* contentH = EvalExpr( env, @"Get ( WindowContentHeight )" );
    __block CGFloat viewH = 0;
    NSString* window = [cmd[@"window"] isKindOfClass:[NSString class]] ? cmd[@"window"] : @"";
    RunOnMain( ^{ viewH = FindWindow( window ).contentView.bounds.size.height; } );
    CGFloat offset = (contentH.doubleValue > 0 && viewH > contentH.doubleValue) ? viewH - contentH.doubleValue : 0;

    CGFloat pad = cmd[@"pad"] ? [cmd[@"pad"] doubleValue] : 4;
    CGFloat l = [nums[0] doubleValue], t = [nums[1] doubleValue];
    CGFloat r = [nums[2] doubleValue], b = [nums[3] doubleValue];
    NSRect region = NSMakeRect( l - pad, t + offset - pad, (r - l) + 2 * pad, (b - t) + 2 * pad );
    NSMutableDictionary* out = [SnapshotCommand( cmd, region ) mutableCopy];
    if ([out[@"ok"] boolValue])
    {
        NSMutableDictionary* res = [out[@"result"] mutableCopy];
        res[@"objectBounds"] = bounds;
        res[@"toolbarOffset"] = @(offset);
        out[@"result"] = res;
    }
    return out;
}

// Execute one parsed command; returns a JSON-serializable result dictionary.
static NSDictionary* ExecuteChannelCommand( NSDictionary* cmd, const fmx::ExprEnv& env )
{
    NSString* verb = [cmd[@"cmd"] isKindOfClass:[NSString class]] ? cmd[@"cmd"] : @"";
    NSString* (^S)(NSString*) = ^NSString*( NSString* key ) {
        id v = cmd[key];
        return [v isKindOfClass:[NSString class]] ? v : @"";
    };

    if (NSDictionary* ui = ExecuteUICommand( cmd )) return ui;

    if ([verb isEqualToString:@"state"])
        return @{ @"ok": @YES, @"result": ParsedJSON( StateJSON( env ) ) };

    if ([verb isEqualToString:@"snapshot"])
        return ObjectSnapshot( cmd, env );

    if ([verb isEqualToString:@"evaluate"])
    {
        NSString* expr = S( @"expr" );
        if (expr.length == 0) return @{ @"ok": @NO, @"error": @"expr required" };
        NSString* v = EvalExpr( env, expr );
        return v ? @{ @"ok": @YES, @"result": v }
                 : @{ @"ok": @NO, @"error": @"evaluation failed" };
    }

    if ([verb isEqualToString:@"sql"])
    {
        NSString* query = S( @"query" );
        if (query.length == 0) return @{ @"ok": @NO, @"error": @"query required" };
        NSString* file = S( @"file" );
        if (file.length == 0) file = EvalExpr( env, @"Get ( FileName )" ) ?: @"";
        fmx::TextUniquePtr queryT, fileT;
        AssignFMXText( *queryT, query );
        AssignFMXText( *fileT, file );
        fmx::DataVectUniquePtr params;
        fmx::DataUniquePtr result;
        const fmx::errcode err = env.ExecuteFileSQLTextResult( *queryT, *fileT, *params, *result, '\t', '\n' );
        if (err != 0)
            return @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"SQL error %d", (int)err] };
        return @{ @"ok": @YES, @"result": NSStringFromFMXText( result->GetAsText() ) };
    }

    if ([verb isEqualToString:@"runscript"])
    {
        NSString* file = S( @"file" );
        if (file.length == 0) file = EvalExpr( env, @"Get ( FileName )" ) ?: @"";
        NSString* r = StartScript( file, S( @"script" ), S( @"param" ), S( @"control" ) );
        if ([r hasPrefix:@"OK"]) return @{ @"ok": @YES, @"result": r };

        // Say what the account actually holds, so a refusal can be diagnosed
        // instead of guessed at (quirk 105).
        NSString* ext = EvalExpr( env, @"Get ( AccountExtendedPrivileges )" ) ?: @"?";
        NSArray* keys = [ext componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]];
        NSMutableDictionary* diag = [@{
            @"file": file,
            @"account": EvalExpr( env, @"Get ( AccountName )" ) ?: @"?",
            @"privilegeSet": EvalExpr( env, @"Get ( AccountPrivilegeSetName )" ) ?: @"?",
            @"extendedPrivileges": keys,
            @"hasFmplugin": @([keys containsObject:@"fmplugin"]),
        } mutableCopy];
        if ([r containsString:@"(825)"])
            diag[@"hint"] = [keys containsObject:@"fmplugin"]
                ? @"825 with fmplugin present: the refusal is not the extended privilege. Check the file name (Get ( FileName ), no extension) and whether the file needs re-opening after the grant."
                : @"825: the signed-in account's privilege set lacks the fmplugin extended privilege; grant it (update:extendedPrivilege) and re-open the file.";
        return @{ @"ok": @NO, @"error": r, @"diagnostics": diag };
    }

    if ([verb isEqualToString:@"help"])
        return @{ @"ok": @YES, @"result": kHelpText };

    if ([verb isEqualToString:@"websnapshot"])
    {
        NSString* path = S( @"path" );
        if (path.length == 0) return @{ @"ok": @NO, @"error": @"path required" };
        NSInteger idx = cmd[@"index"] ? [cmd[@"index"] integerValue] : 0;
        return Outcome( WebViewerSnapshot( S( @"window" ), idx, path ) );
    }

    return @{ @"ok": @NO,
              @"error": [NSString stringWithFormat:@"unknown cmd \"%@\". %@", verb, kHelpText] };
}

// ---- app-level channel (0.5.0) ----------------------------------------------------------
//
// ~/.fm-lens/<app>/_app takes UI commands only, from a timer that keeps
// firing while a modal dialog is up (FileMaker stops idle calls then, so the
// file channel goes silent exactly when a dialog needs dismissing). It also
// works before any file is open. The same config consent governs it: the
// timer does nothing unless this copy of FileMaker has autoArm true.

static NSTimer* gAppChannelTimer = nil;
static NSString* gAppChannelFolder = nil;

static BOOL HostConsents( void )
{
    NSData* raw = [NSData dataWithContentsOfFile:AutoArmConfigPath()];
    NSDictionary* cfg = raw.length ? [NSJSONSerialization JSONObjectWithData:raw options:0 error:nil] : nil;
    if (![cfg isKindOfClass:[NSDictionary class]]) return NO;
    NSDictionary* apps = [cfg[@"apps"] isKindOfClass:[NSDictionary class]] ? cfg[@"apps"] : nil;
    NSDictionary* mine = [apps[HostAppName()] isKindOfClass:[NSDictionary class]] ? apps[HostAppName()] : nil;
    id armVal = (mine && mine[@"autoArm"] != nil) ? mine[@"autoArm"] : cfg[@"autoArm"];
    return [armVal respondsToSelector:@selector(boolValue)] && [armVal boolValue];
}

static void DrainFolder( NSString* folder, NSDictionary* (^execute)(NSDictionary*) );

static void AppChannelTick( void )
{
    static NSTimeInterval lastConsentCheck = 0;
    static BOOL consents = NO;
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - lastConsentCheck > 3.0) { consents = HostConsents(); lastConsentCheck = now; }
    if (!consents) return;

    if (gAppChannelFolder == nil)
    {
        NSString* folder = [[LensRoot() stringByAppendingPathComponent:HostAppName()]
                                stringByAppendingPathComponent:@"_app"];
        for (NSString* sub in @[@"", @"results", @"processed"])
            [[NSFileManager defaultManager]
                createDirectoryAtPath:(sub.length ? [folder stringByAppendingPathComponent:sub] : folder)
                withIntermediateDirectories:YES attributes:nil error:nil];
        gAppChannelFolder = folder;
    }
    DrainFolder( gAppChannelFolder, ^NSDictionary*( NSDictionary* cmd ) {
        if (NSDictionary* ui = ExecuteUICommand( cmd )) return ui;
        NSString* verb = [cmd[@"cmd"] isKindOfClass:[NSString class]] ? cmd[@"cmd"] : @"";
        if ([verb isEqualToString:@"help"]) return @{ @"ok": @YES, @"result": kHelpText };
        return @{ @"ok": @NO, @"error": [NSString stringWithFormat:
                  @"\"%@\" needs a file's calc context; send it to the file channel (~/.fm-lens/<app>/<file>)", verb] };
    } );
}

static void StartAppChannel( void )
{
    dispatch_async( dispatch_get_main_queue(), ^{
        if (gAppChannelTimer) return;
        gAppChannelTimer = [NSTimer timerWithTimeInterval:0.5 repeats:YES block:^(NSTimer*) {
            @try { AppChannelTick(); } @catch (NSException*) {}
        }];
        NSRunLoop* loop = [NSRunLoop mainRunLoop];
        [loop addTimer:gAppChannelTimer forMode:NSRunLoopCommonModes];
        [loop addTimer:gAppChannelTimer forMode:NSModalPanelRunLoopMode];
        [loop addTimer:gAppChannelTimer forMode:NSEventTrackingRunLoopMode];
    } );
}

static void StopAppChannel( void )
{
    RunOnMain( ^{ [gAppChannelTimer invalidate]; gAppChannelTimer = nil; } );
}

static void ChannelIdleTick( void )
{
    // A channel whose folder has been deleted out from under it is DEAD, not
    // armed: without this the plug-in keeps gChannelActive forever, reads an
    // unreadable folder every tick, and auto-arm never fires again (0.4.0 bug,
    // hit live 2026-08-29 by removing a channel folder during a test).
    if (gChannelActive && gChannelFolder.length > 0)
    {
        BOOL isDir = NO;
        if (![[NSFileManager defaultManager] fileExistsAtPath:gChannelFolder isDirectory:&isDir] || !isDir)
        {
            gChannelActive = NO;
            gChannelAutoArmed = NO;
            gChannelLastError = @"channel folder disappeared — disarmed";
        }
    }

    // An AUTO-armed channel follows the frontmost file (0.5.0): once another
    // file is in front, disarm so auto-arm can re-arm for it. Before this, the
    // first file to arm held the channel for the life of the process, even
    // after it closed (quirk 66). Manually armed channels are left alone.
    if (gChannelActive && gChannelAutoArmed)
    {
        static NSTimeInterval lastFollowCheck = 0;
        NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
        if (now - lastFollowCheck > 2.0)
        {
            lastFollowCheck = now;
            fmx::ExprEnvUniquePtr fenv;
            FMX_SetToCurrentEnv( &(*fenv) );
            NSString* front = EvalExpr( *fenv, @"Get ( FileName )" );
            if (front.length && gChannelFile.length && ![front isEqualToString:gChannelFile])
            {
                gChannelActive = NO;
                gChannelAutoArmed = NO;
                gChannelFile = nil;
                gAutoArmLastCheck = 0;   // re-arm on this tick, not in 3 s
            }
        }
    }

    if (!gChannelActive || gChannelFolder.length == 0)
    {
        // not armed — see whether the auto-arm config wants us to be.
        // needs an env (to read Get(FileName)); build one just as the
        // command loop below does.
        if (!gChannelActive)
        {
            fmx::ExprEnvUniquePtr aenv;
            FMX_SetToCurrentEnv( &(*aenv) );
            AutoArmIdleCheck( *aenv );
        }
        if (!gChannelActive || gChannelFolder.length == 0) return;
    }

    // one environment for the whole tick
    fmx::ExprEnvUniquePtr env;
    FMX_SetToCurrentEnv( &(*env) );
    const fmx::ExprEnv& envRef = *env;
    DrainFolder( gChannelFolder, ^NSDictionary*( NSDictionary* cmd ) {
        return ExecuteChannelCommand( cmd, envRef );
    } );
}

// Run up to five *.json commands from folder: result to results/<name>,
// command moved to processed/<name>. A bad file still gets a result.
static void DrainFolder( NSString* folder, NSDictionary* (^execute)(NSDictionary*) )
{
    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSArray<NSString*>* entries = [fmgr contentsOfDirectoryAtPath:folder error:nil];
    if (entries.count == 0) return;

    NSMutableArray<NSString*>* commands = [NSMutableArray array];
    for (NSString* name in [entries sortedArrayUsingSelector:@selector(compare:)])
    {
        if ([name hasPrefix:@"."]) continue;
        if (![name.pathExtension isEqualToString:@"json"]) continue;
        [commands addObject:name];
        if (commands.count >= 5) break;   // bound the work per tick
    }

    for (NSString* name in commands)
    {
        NSString* cmdPath = [folder stringByAppendingPathComponent:name];
        NSData* raw = [NSData dataWithContentsOfFile:cmdPath];
        NSError* jerr = nil;
        NSDictionary* cmd = raw.length
            ? [NSJSONSerialization JSONObjectWithData:raw options:0 error:&jerr] : nil;

        NSDictionary* result;
        if (![cmd isKindOfClass:[NSDictionary class]])
        {
            result = @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"bad command file: %@",
                        jerr.localizedDescription ?: @"not a JSON object"] };
        }
        else
        {
            @try       { result = execute( cmd ); }
            @catch (NSException* ex)
            {
                result = @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"exception: %@", ex.reason] };
            }
        }

        NSMutableDictionary* full = [result mutableCopy];
        full[@"command"] = name;
        NSData* out = [NSJSONSerialization dataWithJSONObject:full options:NSJSONWritingPrettyPrinted error:nil];
        NSString* resultPath = [[folder stringByAppendingPathComponent:@"results"]
                                    stringByAppendingPathComponent:name];
        [out writeToFile:resultPath options:NSDataWritingAtomic error:nil];

        NSString* donePath = [[folder stringByAppendingPathComponent:@"processed"]
                                    stringByAppendingPathComponent:name];
        [fmgr removeItemAtPath:donePath error:nil];
        NSError* merr = nil;
        if (![fmgr moveItemAtPath:cmdPath toPath:donePath error:&merr])
        {
            gChannelLastError = merr.localizedDescription;
            [fmgr removeItemAtPath:cmdPath error:nil];   // never reprocess
        }
        gChannelProcessed++;
    }
}

// ---- calc function entry points ---------------------------------------------------------

static FMX_PROC(fmx::errcode) Do_FMLens_Version( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, @(kVersionString) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_WindowList( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    __block NSString* json = @"[]";
    RunOnMain( ^{
        NSMutableArray* arr = [NSMutableArray array];
        for (NSWindow* w in [NSApp orderedWindows])
        {
            if (w.title.length == 0 && !w.isVisible) continue;
            [arr addObject:@{
                @"title":    w.title ?: @"",
                @"visible":  @(w.isVisible),
                @"main":     @(w.isMainWindow),
                @"key":      @(w.isKeyWindow),
                @"miniaturized": @(w.isMiniaturized),
                @"sheet":    @(w.attachedSheet != nil),
                @"class":    NSStringFromClass( w.class ),
                @"width":    @((int)w.frame.size.width),
                @"height":   @((int)w.frame.size.height),
            }];
        }
        json = JSONString( arr );
    } );
    SetTextResult( results, json );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_WindowSnapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* title = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    SetTextResult( results, SnapshotByTitle( title, NSZeroRect, 0, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_Snapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );

    NSString* window = @"";
    NSRect region = NSZeroRect;
    CGFloat scale = 0;
    if (dataVect.Size() >= 2)
    {
        NSString* optsStr = NSStringFromFMXText( dataVect.At( 1 ).GetAsText() );
        NSDictionary* opts = optsStr.length
            ? [NSJSONSerialization JSONObjectWithData:[optsStr dataUsingEncoding:NSUTF8StringEncoding]
                                              options:0 error:nil] : nil;
        if (![opts isKindOfClass:[NSDictionary class]] && optsStr.length)
        {
            SetTextResult( results, @"ERROR: options must be a JSON object, e.g. {\"window\":\"Contacts\",\"scale\":1}" );
            return 0;
        }
        if ([opts[@"window"] isKindOfClass:[NSString class]]) window = opts[@"window"];
        if (opts[@"w"] && opts[@"h"])
            region = NSMakeRect( [opts[@"x"] doubleValue], [opts[@"y"] doubleValue],
                                 [opts[@"w"] doubleValue], [opts[@"h"] doubleValue] );
        if (opts[@"scale"]) scale = [opts[@"scale"] doubleValue];
    }
    SetTextResult( results, SnapshotByTitle( window, region, scale, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_WebViewerSnapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* title = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    NSInteger idx   = (dataVect.Size() >= 3) ? (NSInteger)dataVect.At( 2 ).GetAsNumber().AsLong() : 0;
    SetTextResult( results, WebViewerSnapshot( title, idx, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_WebViewerList( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    NSString* title = (dataVect.Size() >= 1) ? NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) : @"";
    SetTextResult( results, WebViewerListJSON( title ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_State( short, const fmx::ExprEnv& env, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, StateJSON( env ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_RunScript( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 2) { SetTextResult( results, @"ERROR: fileName and scriptName required" ); return 0; }
    NSString* file    = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* script  = NSStringFromFMXText( dataVect.At( 1 ).GetAsText() );
    NSString* param   = (dataVect.Size() >= 3) ? NSStringFromFMXText( dataVect.At( 2 ).GetAsText() ) : @"";
    NSString* control = (dataVect.Size() >= 4) ? NSStringFromFMXText( dataVect.At( 3 ).GetAsText() ) : @"";
    SetTextResult( results, StartScript( file, script, param, control ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ClipboardFormats( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, ClipboardFormatsJSON() );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ClipboardGetXML( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    NSString* code = (dataVect.Size() >= 1) ? NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) : @"";
    SetTextResult( results, ClipboardGetXML( code ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ClipboardSetXML( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: xml parameter required" ); return 0; }
    NSString* xml  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* code = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    SetTextResult( results, ClipboardSetXML( xml, code ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ChannelStart( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: folder parameter required" ); return 0; }
    SetTextResult( results, ChannelStart( NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ChannelStop( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    gChannelActive = NO;
    gChannelAutoArmed = NO;
    // suppress auto-arm until the config file is edited again (or FileMaker
    // restarts): record the current config mtime as the suppression floor.
    NSDictionary* attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:AutoArmConfigPath() error:nil];
    gAutoArmSuppressMtime = attrs
        ? [(NSDate*)attrs[NSFileModificationDate] timeIntervalSinceReferenceDate]
        : [NSDate timeIntervalSinceReferenceDate];
    SetTextResult( results, @"OK: channel stopped" );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_FMLens_ChannelStatus( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, ChannelStatusJSON() );
    return 0;
}

// ---- registration -----------------------------------------------------------------------

struct FuncDef { short id; const char* name; const char* definition; const char* description;
                 fmx::uint32 minArgs; fmx::uint32 maxArgs; fmx::ExtPluginType func; };

static const FuncDef kFuncs[] = {
    { kFML_VersionID,           "FMLens_Version",            "FMLens_Version",
      "Returns the FM Lens plug-in version", 0, 0, Do_FMLens_Version },
    { kFML_WindowListID,        "FMLens_WindowList",         "FMLens_WindowList",
      "Returns a JSON array describing FileMaker's open windows", 0, 0, Do_FMLens_WindowList },
    { kFML_WindowSnapshotID,    "FMLens_WindowSnapshot",     "FMLens_WindowSnapshot( path { ; windowTitle } )",
      "Writes a PNG of a FileMaker window's content to path; frontmost titled window when no title given", 1, 2, Do_FMLens_WindowSnapshot },
    { kFML_SnapshotID,          "FMLens_Snapshot",           "FMLens_Snapshot( path { ; optionsJSON } )",
      "Window snapshot with JSON options: window (title match), x/y/w/h region in points, scale", 1, 2, Do_FMLens_Snapshot },
    { kFML_WebViewerSnapshotID, "FMLens_WebViewerSnapshot",  "FMLens_WebViewerSnapshot( path { ; windowTitle ; index } )",
      "Writes a PNG of a web viewer's rendered content (WKWebView snapshot)", 1, 3, Do_FMLens_WebViewerSnapshot },
    { kFML_WebViewerListID,     "FMLens_WebViewerList",      "FMLens_WebViewerList( { windowTitle } )",
      "Returns JSON of a window's web viewers: index, url, size, loading", 0, 1, Do_FMLens_WebViewerList },
    { kFML_StateID,             "FMLens_State",              "FMLens_State",
      "Returns JSON of the current context: file, layout, mode, found count, errors, modal-dialog/sheet wedge diagnostics, channel state", 0, 0, Do_FMLens_State },
    { kFML_RunScriptID,         "FMLens_RunScript",          "FMLens_RunScript( fileName ; scriptName { ; parameter ; control } )",
      "Queues a FileMaker script; control: resume (default), halt, exit, pause", 2, 4, Do_FMLens_RunScript },
    { kFML_ClipboardFormatsID,  "FMLens_ClipboardFormats",   "FMLens_ClipboardFormats",
      "Returns JSON of clipboard flavors, flagging FileMaker XML types", 0, 0, Do_FMLens_ClipboardFormats },
    { kFML_ClipboardGetXMLID,   "FMLens_ClipboardGetXML",    "FMLens_ClipboardGetXML( { fmCode } )",
      "Returns FileMaker XML from the clipboard (XMSS, XMSC, XML2, XMTB, XMFD, XMVL, XMFN)", 0, 1, Do_FMLens_ClipboardGetXML },
    { kFML_ClipboardSetXMLID,   "FMLens_ClipboardSetXML",    "FMLens_ClipboardSetXML( xml { ; fmCode } )",
      "Puts FileMaker XML onto the clipboard; flavor inferred from the XML when no code given", 1, 2, Do_FMLens_ClipboardSetXML },
    { kFML_ChannelStartID,      "FMLens_ChannelStart",       "FMLens_ChannelStart( folder )",
      "Arms the drop-folder command channel: <folder>/*.json commands run on idle, results in <folder>/results", 1, 1, Do_FMLens_ChannelStart },
    { kFML_ChannelStopID,       "FMLens_ChannelStop",        "FMLens_ChannelStop",
      "Disarms the command channel", 0, 0, Do_FMLens_ChannelStop },
    { kFML_ChannelStatusID,     "FMLens_ChannelStatus",      "FMLens_ChannelStatus",
      "Returns JSON channel status: active, folder, processed count, last error", 0, 0, Do_FMLens_ChannelStatus },
};

static fmx::ptrtype Do_PluginInit( fmx::int16 version )
{
    fmx::ptrtype result( static_cast<fmx::ptrtype>(kDoNotEnable) );
    const fmx::QuadCharUniquePtr pluginID( kADTh[0], kADTh[1], kADTh[2], kADTh[3] );
    fmx::uint32 flags( fmx::ExprEnv::kDisplayInAllDialogs | fmx::ExprEnv::kFutureCompatible );

    if (version >= k150ExtnVersion)
    {
        bool allOK = true;
        for (const FuncDef& f : kFuncs)
        {
            fmx::TextUniquePtr name, definition, description;
            name->Assign( f.name, fmx::Text::kEncoding_UTF8 );
            definition->Assign( f.definition, fmx::Text::kEncoding_UTF8 );
            description->Assign( f.description, fmx::Text::kEncoding_UTF8 );
            if (fmx::ExprEnv::RegisterExternalFunctionEx( *pluginID, f.id, *name, *definition, *description,
                                                          f.minArgs, f.maxArgs, flags, f.func ) != 0)
            {
                allOK = false;
            }
        }
        if (allOK)
        {
            result = kCurrentExtnVersion;
            StartAppChannel();
        }
    }
    return result;
}

static void Do_PluginShutdown( fmx::int16 version )
{
    StopAppChannel();
    const fmx::QuadCharUniquePtr pluginID( kADTh[0], kADTh[1], kADTh[2], kADTh[3] );
    if (version >= k140ExtnVersion)
    {
        for (const FuncDef& f : kFuncs)
            static_cast<void>(fmx::ExprEnv::UnRegisterExternalFunction( *pluginID, f.id ));
    }
}

// ---- boilerplate ------------------------------------------------------------------------

static void CopyUTF8StrToUnichar16Str( const char* inStr, fmx::uint32 outStrSize, fmx::unichar16* outStr )
{
    fmx::TextUniquePtr txt;
    txt->Assign( inStr, fmx::Text::kEncoding_UTF8 );
    const fmx::uint32 txtSize( (outStrSize <= txt->GetSize()) ? (outStrSize - 1) : txt->GetSize() );
    txt->GetUnicode( outStr, 0, txtSize );
    outStr[txtSize] = 0;
}

static void Do_GetString( fmx::uint32 whichString, fmx::uint32, fmx::uint32 outBufferSize, fmx::unichar16* outBuffer )
{
    switch (whichString)
    {
        case kFMXT_NameStr:
            CopyUTF8StrToUnichar16Str( "FM Lens", outBufferSize, outBuffer );
            break;
        case kFMXT_AppConfigStr:
            CopyUTF8StrToUnichar16Str( "FM Lens: agent eyes and hands in FileMaker Pro. Snapshots, state, menus, dialogs, scripts, XML clipboard, command channels", outBufferSize, outBuffer );
            break;
        case kFMXT_OptionsStr:
            CopyUTF8StrToUnichar16Str( kADTh, outBufferSize, outBuffer );
            outBuffer[4] = '1';   // always "1"
            outBuffer[5] = 'n';   // no Configure button
            outBuffer[6] = 'n';   // always "n"
            outBuffer[7] = 'Y';   // wants Init/Shutdown
            outBuffer[8] = 'Y';   // wants Idle (command channel)
            outBuffer[9] = 'n';   // no session/file shutdown messages
            outBuffer[10] = 'n';  // always "n"
            outBuffer[11] = 0;
            break;
        default:
            outBuffer[0] = 0;
            break;
    }
}

FMX_ExternCallPtr gFMX_ExternCallPtr( nullptr );

void FMX_ENTRYPT FMExternCallProc( FMX_ExternCallPtr pb )
{
    gFMX_ExternCallPtr = pb;
    switch (pb->whichCall)
    {
        case kFMXT_Init:
            pb->result = Do_PluginInit( pb->extnVersion );
            break;
        case kFMXT_Idle:
            if (!pb->unsafeCalls && pb->parm1 != kFMXT_Unsafe)
                ChannelIdleTick();
            break;
        case kFMXT_Shutdown:
            Do_PluginShutdown( pb->extnVersion );
            break;
        case kFMXT_GetString:
            Do_GetString( static_cast<fmx::uint32>(pb->parm1), static_cast<fmx::uint32>(pb->parm2),
                          static_cast<fmx::uint32>(pb->parm3), reinterpret_cast<fmx::unichar16*>(pb->result) );
            break;
        default:
            break;
    }
}
